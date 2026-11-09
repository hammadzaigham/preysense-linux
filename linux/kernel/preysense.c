// SPDX-License-Identifier: GPL-2.0-only
/* Narrow Acer Gaming WMI bridge plus bounded ERM4 GPU-offset MMIO for PHN16S-71. */
#include <linux/module.h>
#include <linux/acpi.h>
#include <linux/dmi.h>
#include <linux/platform_device.h>
#include <linux/mutex.h>
#include <linux/unaligned.h>
#include <linux/workqueue.h>
#include <linux/suspend.h>
#include <linux/power_supply.h>
#include <linux/input.h>
#include <linux/ktime.h>
#include <linux/io.h>
#include <linux/delay.h>
#include <asm/msr.h>

#define GAMING_GUID "7A4DDFE7-5B5D-40B4-8595-4408E0CC7F56"
static DEFINE_MUTEX(gate);
static struct platform_device *pdev;
static DEFINE_MUTEX(control_gate);
static bool manual_active;
static int last_cpu = -1, last_gpu = -1;
static unsigned long manual_deadline;
static struct delayed_work fan_watchdog;


/* Expose dedicated shortcuts and aggregate idle time, never ordinary key identities. */
static atomic_t predator_events = ATOMIC_INIT(0);
static atomic64_t keyboard_activity_ns;
static DEFINE_SPINLOCK(shortcut_gate);
static bool predator_held, predator_combo;
static unsigned int shortcut_serial, shortcut_number, overlay_serial, consumed_shortcuts;
/* Input filters may run atomically; notify sysfs waiters from process context. */
static struct work_struct shortcut_notify_work;
static void shortcut_notify_fn(struct work_struct *work)
{
    sysfs_notify(&pdev->dev.kobj, NULL, "predator_events");
    sysfs_notify(&pdev->dev.kobj, NULL, "shortcut_events");
}
static bool preysense_key_filter(struct input_handle *handle, unsigned int type,
                                unsigned int code, int value)
{
    unsigned long flags;
    bool filtered = false, notify = false;
    int index;
    if (type != EV_KEY) return false;
    if (value == 1) atomic64_set(&keyboard_activity_ns, ktime_get_boottime_ns());
    spin_lock_irqsave(&shortcut_gate, flags);
    if (handle->private && code == KEY_PROG3) {
        filtered = true;
        if (value == 1) { predator_held = true; predator_combo = false; }
        else if (value == 0) {
            if (predator_held && !predator_combo) { atomic_inc(&predator_events); notify = true; }
            predator_held = false;
        }
    } else {
        index = code == KEY_R ? 5 : (code >= KEY_1 && code <= KEY_5 ? code - KEY_1 : -1);
        if (index >= 0) {
            if (predator_held && value == 1) {
                predator_combo = true;
                consumed_shortcuts |= BIT(index);
                notify = true;
                if (index == 5) overlay_serial++;
                else { shortcut_number = index + 1; shortcut_serial++; }
                filtered = true;
            } else if (consumed_shortcuts & BIT(index)) {
                filtered = true;
                if (value == 0) consumed_shortcuts &= ~BIT(index);
            }
        }
    }
    spin_unlock_irqrestore(&shortcut_gate, flags);
    if (notify) schedule_work(&shortcut_notify_work);
    return filtered;
}
static void reset_shortcut_state(void)
{
    unsigned long flags;
    spin_lock_irqsave(&shortcut_gate, flags);
    predator_held = false; predator_combo = false; consumed_shortcuts = 0;
    spin_unlock_irqrestore(&shortcut_gate, flags);
}
static int preysense_key_connect(struct input_handler *handler, struct input_dev *dev,
                                const struct input_device_id *id)
{
    struct input_handle *handle;
    int ret;
    bool acer = dev->name && (!strcmp(dev->name, "AT Translated Set 2 keyboard") ||
                              !strcmp(dev->name, "Acer WMI hotkeys"));
    if (!acer && !(test_bit(KEY_A, dev->keybit) && test_bit(KEY_Z, dev->keybit))) return -ENODEV;
    handle = kzalloc(sizeof(*handle), GFP_KERNEL);
    if (!handle) return -ENOMEM;
    handle->dev = dev; handle->handler = handler; handle->name = "preysense-key";
    handle->private = acer ? (void *)1UL : NULL;
    ret = input_register_handle(handle);
    if (ret) goto fail;
    ret = input_open_device(handle);
    if (ret) { input_unregister_handle(handle); goto fail; }
    return 0;
fail:
    kfree(handle); return ret;
}
static void preysense_key_disconnect(struct input_handle *handle)
{
    if (handle->private) reset_shortcut_state();
    input_close_device(handle); input_unregister_handle(handle); kfree(handle);
}
static const struct input_device_id preysense_key_ids[] = {
    { .flags = INPUT_DEVICE_ID_MATCH_EVBIT, .evbit = { BIT_MASK(EV_KEY) } },
    { }
};
static struct input_handler preysense_keys = {
    .filter = preysense_key_filter, .connect = preysense_key_connect,
    .disconnect = preysense_key_disconnect, .name = "preysense-keys",
    .id_table = preysense_key_ids,
};
static ssize_t predator_events_show(struct device *dev, struct device_attribute *a, char *buf)
{
    return sysfs_emit(buf, "%d\n", atomic_read(&predator_events));
}
static DEVICE_ATTR_RO(predator_events);
static ssize_t event_notifications_show(struct device *dev, struct device_attribute *a, char *buf)
{
    return sysfs_emit(buf, "1\n");
}
static DEVICE_ATTR_RO(event_notifications);
static ssize_t predator_down_show(struct device *dev, struct device_attribute *a, char *buf)
{
    unsigned long flags; bool held;
    spin_lock_irqsave(&shortcut_gate, flags); held = predator_held; spin_unlock_irqrestore(&shortcut_gate, flags);
    return sysfs_emit(buf, "%u\n", held);
}
static DEVICE_ATTR_RO(predator_down);
static ssize_t shortcut_events_show(struct device *dev, struct device_attribute *a, char *buf)
{
    unsigned long flags;
    unsigned int serial, number, overlay;
    spin_lock_irqsave(&shortcut_gate, flags);
    serial = shortcut_serial; number = shortcut_number; overlay = overlay_serial;
    spin_unlock_irqrestore(&shortcut_gate, flags);
    return sysfs_emit(buf, "%u %u %u\n", serial, number, overlay);
}
static DEVICE_ATTR_RO(shortcut_events);
static ssize_t keyboard_idle_ms_show(struct device *dev, struct device_attribute *a, char *buf)
{
    u64 idle = ktime_get_boottime_ns() - atomic64_read(&keyboard_activity_ns);
    return sysfs_emit(buf, "%llu\n", div_u64(idle, NSEC_PER_MSEC));
}
static DEVICE_ATTR_RO(keyboard_idle_ms);

static int call_wmi(const char *guid, u32 method, u64 value, bool wide, u64 *answer, bool check_status)
{
	struct acpi_buffer in = { wide ? 8 : 4, &value };
	struct acpi_buffer out = { ACPI_ALLOCATE_BUFFER, NULL };
	union acpi_object *obj;
	acpi_status status;
	int ret = 0;
	mutex_lock(&gate);
	status = wmi_evaluate_method(guid, 0, method, &in, &out);
	obj = out.pointer;
	if (ACPI_FAILURE(status) || !obj) { ret = -EIO; goto done; }
	if (obj->type == ACPI_TYPE_INTEGER) *answer = obj->integer.value;
	else if (obj->type == ACPI_TYPE_BUFFER && obj->buffer.length >= 8)
		*answer = get_unaligned_le64(obj->buffer.pointer);
	else if (obj->type == ACPI_TYPE_BUFFER && obj->buffer.length >= 4)
		*answer = get_unaligned_le32(obj->buffer.pointer);
	else ret = -EPROTO;
	if (!ret && check_status && (*answer & 0xff)) ret = -EREMOTEIO;
done:
	kfree(out.pointer);
	mutex_unlock(&gate);
	return ret;
}

static int gaming(u32 method, u64 value, bool wide, u64 *answer)
{
    return call_wmi(GAMING_GUID, method, value, wide, answer, true);
}
/* Manual fan ownership expires unless refreshed by userspace every eight seconds. */
static void restore_auto(void)
{
    u64 out;
    if (gaming(14, 0x410009, true, &out)) {
        pr_err_ratelimited("preysense: failed to restore automatic fans; retrying\n");
        manual_deadline = jiffies + HZ;
        return;
    }
    manual_active = false;
    last_cpu = last_gpu = -1;
}
static void fan_watchdog_fn(struct work_struct *work)
{
    mutex_lock(&control_gate);
    if (manual_active && time_after_eq(jiffies, manual_deadline)) restore_auto();
    if (manual_active) schedule_delayed_work(&fan_watchdog, HZ);
    mutex_unlock(&control_gate);
}
static int sleep_event(struct notifier_block *block, unsigned long event, void *unused)
{
    if (event == PM_SUSPEND_PREPARE || event == PM_HIBERNATION_PREPARE) {
        reset_shortcut_state();
        mutex_lock(&control_gate);
        if (manual_active) restore_auto();
        mutex_unlock(&control_gate);
    }
    return NOTIFY_OK;
}
static struct notifier_block sleep_notifier = { .notifier_call = sleep_event };
static ssize_t fan_duty_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
    unsigned int cpu, gpu; char extra; u64 out, temperature; int ret = 0;
    if (sscanf(buf, "%u %u %c", &cpu, &gpu, &extra) != 2 || cpu > 100 || gpu > 100) return -EINVAL;
    mutex_lock(&control_gate);
    /* Unchanged targets only renew the watchdog lease; no duplicate EC read. */
    if (!manual_active || last_cpu != cpu || last_gpu != gpu) {
        ret = gaming(5, 0x101, true, &temperature);
        if (ret || !((temperature >> 8) & 65535)) {
            restore_auto();
            if (!ret) ret = -ENODATA;
            goto done;
        }
    }
    if (!manual_active) {
        ret = gaming(14, 0xc30009, true, &out);
        if (ret) goto done;
        manual_active = true;
        last_cpu = last_gpu = -1;
    }
    if (last_cpu != cpu) {
        ret = gaming(16, 1 | (cpu << 8), true, &out);
        if (ret) goto fail;
        last_cpu = cpu;
    }
    if (last_gpu != gpu) {
        ret = gaming(16, 4 | (gpu << 8), true, &out);
        if (ret) goto fail;
        last_gpu = gpu;
    }
    manual_deadline = jiffies + 8 * HZ;
    mod_delayed_work(system_wq, &fan_watchdog, HZ);
    goto done;
fail:
    restore_auto();
done:
    if (ret && manual_active) mod_delayed_work(system_wq, &fan_watchdog, HZ);
    mutex_unlock(&control_gate);
    return ret ? ret : count;
}
static DEVICE_ATTR(fan_duty, 0220, NULL, fan_duty_store);
#define BATTERY_GUID "79772EC5-04B1-4BFD-843C-61E7F77B6CC9"
static ssize_t battery_limit_show(struct device *dev, struct device_attribute *a, char *buf)
{
    u64 out; int ret = call_wmi(BATTERY_GUID, 20, 0x101, false, &out, false);
    if (ret) return ret;
    if (!(out & 1)) return -EOPNOTSUPP;
    return sysfs_emit(buf, "%d\n", (out >> 24) & 255 ? 80 : 100);
}
static ssize_t battery_limit_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
    unsigned int value; u64 out; int ret;
    if (kstrtouint(buf, 10, &value) || (value != 80 && value != 100)) return -EINVAL;
    ret = call_wmi(BATTERY_GUID, 20, 0x101, false, &out, false);
    if (ret) return ret;
    if (!(out & 1)) return -EOPNOTSUPP;
    ret = call_wmi(BATTERY_GUID, 21, 0x101 | ((u64)(value == 80) << 16), true, &out, true);
    return ret ? ret : count;
}
static DEVICE_ATTR(battery_limit, 0664, battery_limit_show, battery_limit_store);

#define APGE_GUID "61EF69EA-865C-4BC3-A502-A0DEBA0CB531"
static ssize_t boot_sound_show(struct device *dev, struct device_attribute *a, char *buf)
{
    u64 out; int ret = gaming(23, 6, true, &out);
    return ret ? ret : sysfs_emit(buf, "%u\n", (unsigned int)((out >> 8) & 1));
}
static ssize_t boot_sound_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
    unsigned int value; u64 out; int ret;
    if (kstrtouint(buf, 10, &value) || value > 1) return -EINVAL;
    ret = gaming(22, 6 | (value << 8), true, &out);
    return ret ? ret : count;
}
static DEVICE_ATTR(boot_sound, 0664, boot_sound_show, boot_sound_store);
static ssize_t led_timeout_show(struct device *dev, struct device_attribute *a, char *buf)
{
    u64 out; int ret = call_wmi(APGE_GUID, 2, 0x88401, true, &out, false);
    if (ret) return ret;
    if (out == 0 || out == 0x80000) return sysfs_emit(buf, "0\n");
    return sysfs_emit(buf, "%u\n", (unsigned int)((out >> 40) & 0xff));
}
static ssize_t led_timeout_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
    unsigned int value; u64 out; int ret;
    if (kstrtouint(buf, 10, &value) || value > 120) return -EINVAL;
    ret = call_wmi(APGE_GUID, 1, value ? (((u64)value << 40) | 0x88402ULL) : 0x88402ULL, true, &out, false);
    if (!ret && out) ret = -EREMOTEIO;
    return ret ? ret : count;
}
static DEVICE_ATTR(led_timeout, 0664, led_timeout_show, led_timeout_store);
static ssize_t usb_charging_show(struct device *dev, struct device_attribute *a, char *buf)
{
    u64 out; unsigned int mode, threshold;
    int ret = call_wmi(APGE_GUID, 2, 4, true, &out, true);
    if (ret) return ret;
    mode = (out >> 8) & 255; threshold = (out >> 16) & 255;
    if ((mode != 15 && mode != 31) || (threshold != 10 && threshold != 20 && threshold != 30)) return -EPROTO;
    return sysfs_emit(buf, "%u\n", mode == 15 ? threshold : 0);
}
static ssize_t usb_charging_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
    unsigned int value; u64 out; int ret;
    if (kstrtouint(buf, 10, &value) || (value != 0 && value != 10 && value != 20 && value != 30)) return -EINVAL;
    ret = call_wmi(APGE_GUID, 1, 4 | ((value ? 15ULL : 31ULL) << 8) | ((value ? (u64)value : 10ULL) << 16), true, &out, false);
    if (!ret && out) ret = -EREMOTEIO;
    return ret ? ret : count;
}
static DEVICE_ATTR(usb_charging, 0664, usb_charging_show, usb_charging_store);
static ssize_t lcd_overdrive_show(struct device *dev, struct device_attribute *a, char *buf)
{
    u64 out; int ret = gaming(3, 0, true, &out);
    if (ret) return ret;
    if (!(out & BIT_ULL(24))) return -EOPNOTSUPP;
    return sysfs_emit(buf, "%u\n", !!(out & BIT_ULL(48)));
}
static ssize_t lcd_overdrive_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
    unsigned int value; u64 out; int ret;
    if (kstrtouint(buf, 10, &value) || value > 1) return -EINVAL;
    ret = gaming(1, value ? 0x1000000000010ULL : 0x10, true, &out);
    return ret ? ret : count;
}
static DEVICE_ATTR(lcd_overdrive, 0664, lcd_overdrive_show, lcd_overdrive_store);
static ssize_t profile_show(struct device *dev, struct device_attribute *a, char *buf)
{
	u64 out; int ret = gaming(23, 11, false, &out);
	return ret ? ret : sysfs_emit(buf, "%llu\n", (out >> 8) & 255);
}
static ssize_t profile_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
	unsigned int value; u64 out; int ret;
	if (kstrtouint(buf, 10, &value) || (value != 0 && value != 1 && value != 4 && value != 5 && value != 6)) return -EINVAL;
	if ((value == 4 || value == 5) && power_supply_is_system_supplied() <= 0) return -EPERM;
    mutex_lock(&control_gate);
    if (manual_active) restore_auto();
    ret = gaming(22, 11 | (value << 8), true, &out);
    mutex_unlock(&control_gate);
	return ret ? ret : count;
}
static DEVICE_ATTR(profile, 0664, profile_show, profile_store);

/* BIOS display mux, NOT NVIDIA Dynamic Display Switching. Takes effect at POST.
 * OEM firmware: 1 = Optimus, 2 = discrete, 3 = automatic. Keep the raw enum
 * here rather than reusing the differently ordered Windows UI enum.
 */
static ssize_t gpu_mux_show(struct device *dev, struct device_attribute *a, char *buf)
{
    u64 out; unsigned int mode;
    int ret = gaming(23, 2, false, &out);
    if (ret) return ret;
    mode = (out >> 8) & 255;
    if (mode < 1 || mode > 3) return -EOPNOTSUPP;
    return sysfs_emit(buf, "%u\n", mode);
}
static ssize_t gpu_mux_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
    unsigned int value; u64 out; int ret;
    if (kstrtouint(buf, 10, &value) || value < 1 || value > 3) return -EINVAL;
    /* Verify that this firmware implements the getter before staging anything. */
    ret = gaming(23, 2, false, &out);
    if (ret) return ret;
    if (((out >> 8) & 255) < 1 || ((out >> 8) & 255) > 3) return -EOPNOTSUPP;
    ret = gaming(22, 2 | (value << 8), true, &out);
    return ret ? ret : count;
}
static DEVICE_ATTR(gpu_mux, 0664, gpu_mux_show, gpu_mux_store);

static ssize_t fan_mode_show(struct device *dev, struct device_attribute *a, char *buf)
{
	u64 out; int ret = gaming(15, 9, false, &out);
	return ret ? ret : sysfs_emit(buf, "%llu %llu\n", (out >> 8) & 3, (out >> 14) & 3);
}
static ssize_t fan_mode_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
	unsigned int value; u64 out; int ret;
	if (kstrtouint(buf, 10, &value) || value > 1) return -EINVAL;
	/* 1 = firmware auto, 2 = firmware maximum. Manual deliberately excluded. */
	mutex_lock(&control_gate);
    ret = gaming(14, value ? 0x820009 : 0x410009, true, &out);
    if (!ret) { manual_active = false; last_cpu = last_gpu = -1; }
    mutex_unlock(&control_gate);
	return ret ? ret : count;
}
static DEVICE_ATTR(fan_mode, 0664, fan_mode_show, fan_mode_store);

static ssize_t sensor_show(struct device *dev, struct device_attribute *a, char *buf)
{
	u32 sensor = !strcmp(a->attr.name, "cpu_temp") ? 1 :
		!strcmp(a->attr.name, "gpu_temp") ? 10 :
		!strcmp(a->attr.name, "cpu_fan") ? 2 : 6;
	u64 out; int ret = gaming(5, 1 | (sensor << 8), true, &out);
	return ret ? ret : sysfs_emit(buf, "%llu\n", (out >> 8) & 65535);
}
static DEVICE_ATTR(cpu_temp, 0444, sensor_show, NULL);
static DEVICE_ATTR(gpu_temp, 0444, sensor_show, NULL);
static DEVICE_ATTR(cpu_fan, 0444, sensor_show, NULL);
static DEVICE_ATTR(gpu_fan, 0444, sensor_show, NULL);

/* Requested core VID from IA32_PERF_STATUS[47:32], millivolts (Windows MSR path). */
static ssize_t cpu_vid_mv_show(struct device *dev, struct device_attribute *a, char *buf)
{
	u64 raw;
	u32 code, mv;
	int err = rdmsrl_safe(0x198, &raw);

	if (err)
		return err;
	code = (raw >> 32) & 0xffff;
	mv = (code * 1000u) / 8192u;
	if (!mv || mv > 2500)
		return -ENODATA;
	return sysfs_emit(buf, "%u\n", mv);
}
static DEVICE_ATTR_RO(cpu_vid_mv);

/*
 * Intel TCC/PROCHOT offset (MSR 0x1A2), matching Windows CpuProchotController.
 * Show: "offset tjmax locked". Store: offset 0–63. Preserves other TEMPERATURE_TARGET bits.
 */
#define MSR_TEMPERATURE_TARGET 0x1A2ULL
#define MSR_PLATFORM_INFO 0xCEULL
#define PROCHOT_OFFSET_MASK (0x3FULL << 24)
#define PROCHOT_LOCK_BIT BIT_ULL(31)

static DEFINE_MUTEX(prochot_gate);

static ssize_t cpu_prochot_show(struct device *dev, struct device_attribute *a, char *buf)
{
	u64 raw;
	int err, target, offset;

	mutex_lock(&prochot_gate);
	err = rdmsrl_safe(MSR_TEMPERATURE_TARGET, &raw);
	mutex_unlock(&prochot_gate);
	if (err)
		return err;
	target = (int)((raw >> 16) & 0xFF);
	offset = (int)((raw & PROCHOT_OFFSET_MASK) >> 24);
	if (target < 40 || target > 125 || offset >= target || (raw & BIT_ULL(30)))
		return -ENODATA;
	return sysfs_emit(buf, "%d %d %u\n", offset, target, (raw & PROCHOT_LOCK_BIT) ? 1 : 0);
}

static ssize_t cpu_prochot_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
	unsigned int offset;
	u64 platform, original, desired, actual, current;
	int err, target;
	char extra;

	if (sscanf(buf, "%u %c", &offset, &extra) != 1)
		return -EINVAL;
	if (offset > 63)
		return -EINVAL;

	mutex_lock(&prochot_gate);
	err = rdmsrl_safe(MSR_PLATFORM_INFO, &platform);
	if (err)
		goto out;
	if (!(platform & BIT_ULL(30))) {
		err = -EOPNOTSUPP;
		goto out;
	}
	err = rdmsrl_safe(MSR_TEMPERATURE_TARGET, &original);
	if (err)
		goto out;
	if (original & BIT_ULL(30)) {
		err = -EINVAL;
		goto out;
	}
	target = (int)((original >> 16) & 0xFF);
	if (target < 40 || target > 125 || (int)offset >= target) {
		err = -ERANGE;
		goto out;
	}
	if ((original & PROCHOT_LOCK_BIT) &&
	    (int)((original & PROCHOT_OFFSET_MASK) >> 24) != (int)offset) {
		err = -EPERM;
		goto out;
	}
	desired = (original & ~PROCHOT_OFFSET_MASK) | ((u64)offset << 24);
	if (desired == original) {
		err = 0;
		goto out;
	}
	err = wrmsrl_safe(MSR_TEMPERATURE_TARGET, desired);
	if (!err && !rdmsrl_safe(MSR_TEMPERATURE_TARGET, &actual) && actual == desired) {
		err = 0;
		goto out;
	}
	/* Rejected write may still have changed the register — restore offset only. */
	if (!rdmsrl_safe(MSR_TEMPERATURE_TARGET, &current)) {
		if ((current & PROCHOT_OFFSET_MASK) != (original & PROCHOT_OFFSET_MASK) &&
		    !(current & PROCHOT_LOCK_BIT))
			wrmsrl_safe(MSR_TEMPERATURE_TARGET,
				    (current & ~PROCHOT_OFFSET_MASK) | (original & PROCHOT_OFFSET_MASK));
	}
	err = -EIO;
out:
	mutex_unlock(&prochot_gate);
	return err ? err : count;
}
static DEVICE_ATTR(cpu_prochot, 0664, cpu_prochot_show, cpu_prochot_store);

/*
 * Acer ERM4 GPU profile table (Windows AcerErm4Table / AcerProfileApplyTransaction).
 * Bounded ioremap of the PHN16S-71 Predator signature window only — Secure Boot OK
 * when this module is MOK-signed. Not /dev/mem and not nvidia-smi -pl.
 */
#define ERM4_PHN16S71_BASE 0xFE800400ULL
#define ERM4_WINDOW 0x100
static void __iomem *erm4;
static DEFINE_MUTEX(erm4_gate);

static u16 erm4_db_offset(u8 mode)
{
	switch (mode) {
	case 0: return 0xA4;
	case 1: return 0xAC;
	case 4: return 0xB4;
	case 5: return 0xBC;
	case 6: return 0xC4;
	default: return 0;
	}
}

static bool erm4_signature_ok(void __iomem *base)
{
	static const char sig[] = "Predator";
	unsigned int i;

	for (i = 0; i < sizeof(sig) - 1; i++)
		if (ioread8(base + i) != (u8)sig[i])
			return false;
	return true;
}

static int erm4_map(void)
{
	void __iomem *map = ioremap(ERM4_PHN16S71_BASE, ERM4_WINDOW);

	if (!map)
		return -ENOMEM;
	if (!erm4_signature_ok(map)) {
		iounmap(map);
		return -ENODEV;
	}
	erm4 = map;
	pr_info("preysense: ERM4 GPU offsets at 0x%llx\n", (unsigned long long)ERM4_PHN16S71_BASE);
	return 0;
}

static void erm4_unmap(void)
{
	if (erm4) {
		iounmap(erm4);
		erm4 = NULL;
	}
}

static int acer_mode_get(u8 *mode)
{
	u64 out;
	int ret = gaming(23, 11, false, &out);

	if (ret)
		return ret;
	*mode = (u8)((out >> 8) & 255);
	return 0;
}

static int acer_mode_set(u8 mode)
{
	u64 out;

	return gaming(22, 11 | ((u32)mode << 8), true, &out);
}

static int acer_mode_wait(u8 expected)
{
	int i;
	u8 mode;

	for (i = 0; i < 20; i++) {
		if (!acer_mode_get(&mode) && mode == expected)
			return 0;
		msleep(50);
	}
	return -ETIMEDOUT;
}

static void erm4_read_triplet(u8 mode, u8 *db, u8 *ct, u8 *cp)
{
	u16 off = erm4_db_offset(mode);

	*db = ioread8(erm4 + off);
	*ct = ioread8(erm4 + off + 1);
	*cp = ioread8(erm4 + off + 2);
}

/* Full ERM4 profile record used by Windows DriverFactoryCalibration.CaptureFromErm4:
 * DB base address holds [P1, PL1, Tau, PL2, DB, CT, CP] starting at base-4.
 */
static void erm4_read_profile(u8 mode, u8 *pl1, u8 *tau, u8 *pl2, u8 *db, u8 *ct, u8 *cp)
{
	u16 off = erm4_db_offset(mode);

	*pl1 = ioread8(erm4 + off - 3);
	*tau = ioread8(erm4 + off - 2);
	*pl2 = ioread8(erm4 + off - 1);
	*db = ioread8(erm4 + off);
	*ct = ioread8(erm4 + off + 1);
	*cp = ioread8(erm4 + off + 2);
}

static void erm4_write_triplet(u8 mode, u8 db, u8 ct, u8 cp)
{
	u16 off = erm4_db_offset(mode);

	iowrite8(db, erm4 + off);
	iowrite8(ct, erm4 + off + 1);
	iowrite8(cp, erm4 + off + 2);
}

static bool erm4_verify_triplet(u8 mode, u8 db, u8 ct, u8 cp)
{
	u8 rdb, rct, rcp;

	erm4_read_triplet(mode, &rdb, &rct, &rcp);
	return rdb == db && rct == ct && rcp == cp;
}

static ssize_t gpu_offsets_show(struct device *dev, struct device_attribute *a, char *buf)
{
	static const u8 modes[] = { 0, 1, 4, 5, 6 };
	size_t n = 0;
	unsigned int i;

	if (!erm4)
		return -ENODEV;
	mutex_lock(&erm4_gate);
	for (i = 0; i < ARRAY_SIZE(modes); i++) {
		u8 db, ct, cp;

		erm4_read_triplet(modes[i], &db, &ct, &cp);
		n += scnprintf(buf + n, PAGE_SIZE - n, "%u %u %u %u\n", modes[i], ct, db, cp);
	}
	mutex_unlock(&erm4_gate);
	return n;
}

static ssize_t gpu_offsets_store(struct device *dev, struct device_attribute *a, const char *buf, size_t count)
{
	unsigned int mode, ct, db, cp = 0;
	char extra;
	int matched, ret;
	u8 selected, original, staging, orig_db, orig_ct, orig_cp;
	bool wrote = false;

	if (!erm4)
		return -ENODEV;
	matched = sscanf(buf, "%u %u %u %u %c", &mode, &ct, &db, &cp, &extra);
	if (matched != 3 && matched != 4)
		return -EINVAL;
	if (mode != 0 && mode != 1 && mode != 4 && mode != 5 && mode != 6)
		return -EINVAL;
	if (ct > 100 || ct % 5 || db > 25 || db % 5)
		return -EINVAL;
	if (matched == 4 && (cp > 100 || cp % 5))
		return -EINVAL;

	selected = (u8)mode;
	staging = selected == 4 ? 1 : 4;

	mutex_lock(&control_gate);
	mutex_lock(&erm4_gate);
	if (manual_active)
		restore_auto();
	ret = acer_mode_get(&original);
	if (ret)
		goto out;
	erm4_read_triplet(selected, &orig_db, &orig_ct, &orig_cp);
	if (matched == 3)
		cp = orig_cp;

	if (original == selected) {
		ret = acer_mode_set(staging);
		if (ret)
			goto out;
		ret = acer_mode_wait(staging);
		if (ret)
			goto restore_mode;
	}
	{
		u8 before;

		ret = acer_mode_get(&before);
		if (ret || before == selected) {
			ret = ret ? ret : -EBUSY;
			goto restore_mode;
		}
	}
	wrote = true;
	erm4_write_triplet(selected, (u8)db, (u8)ct, (u8)cp);
	if (!erm4_verify_triplet(selected, (u8)db, (u8)ct, (u8)cp)) {
		ret = -EIO;
		goto rollback;
	}
	msleep(2000);
	ret = acer_mode_set(selected);
	if (ret)
		goto rollback;
	ret = acer_mode_wait(selected);
	if (ret || !erm4_verify_triplet(selected, (u8)db, (u8)ct, (u8)cp)) {
		ret = ret ? ret : -EIO;
		goto rollback;
	}
	ret = 0;
	goto out;

rollback:
	if (wrote) {
		u8 cur;

		if (!acer_mode_get(&cur) && cur == selected)
			acer_mode_set(staging);
		acer_mode_wait(staging);
		erm4_write_triplet(selected, orig_db, orig_ct, orig_cp);
	}
restore_mode:
	acer_mode_set(original);
	acer_mode_wait(original);
out:
	mutex_unlock(&erm4_gate);
	mutex_unlock(&control_gate);
	return ret ? ret : count;
}
static DEVICE_ATTR(gpu_offsets, 0664, gpu_offsets_show, gpu_offsets_store);

static ssize_t gpu_offsets_available_show(struct device *dev, struct device_attribute *a, char *buf)
{
	return sysfs_emit(buf, "%u\n", erm4 ? 1 : 0);
}
static DEVICE_ATTR_RO(gpu_offsets_available);

static ssize_t factory_profiles_show(struct device *dev, struct device_attribute *a, char *buf)
{
	static const u8 modes[] = { 0, 1, 4, 5, 6 };
	size_t n = 0;
	unsigned int i;

	if (!erm4)
		return -ENODEV;
	mutex_lock(&erm4_gate);
	for (i = 0; i < ARRAY_SIZE(modes); i++) {
		u8 pl1, tau, pl2, db, ct, cp;

		erm4_read_profile(modes[i], &pl1, &tau, &pl2, &db, &ct, &cp);
		n += scnprintf(buf + n, PAGE_SIZE - n, "%u %u %u %u %u %u %u\n",
			       modes[i], pl1, tau, pl2, ct, db, cp);
	}
	mutex_unlock(&erm4_gate);
	return n;
}
static DEVICE_ATTR_RO(factory_profiles);

static struct attribute *preysense_attrs[] = { &dev_attr_profile.attr, &dev_attr_fan_mode.attr,
	&dev_attr_cpu_temp.attr, &dev_attr_gpu_temp.attr, &dev_attr_cpu_fan.attr, &dev_attr_gpu_fan.attr, &dev_attr_cpu_vid_mv.attr,
	&dev_attr_cpu_prochot.attr,
	&dev_attr_gpu_offsets.attr, &dev_attr_gpu_offsets_available.attr, &dev_attr_factory_profiles.attr,
	&dev_attr_battery_limit.attr, &dev_attr_fan_duty.attr, &dev_attr_boot_sound.attr, &dev_attr_led_timeout.attr, &dev_attr_usb_charging.attr, &dev_attr_lcd_overdrive.attr, &dev_attr_predator_events.attr, &dev_attr_event_notifications.attr, &dev_attr_predator_down.attr, &dev_attr_keyboard_idle_ms.attr, &dev_attr_shortcut_events.attr, &dev_attr_gpu_mux.attr, NULL };
ATTRIBUTE_GROUPS(preysense);

static int __init preysense_init(void)
{
	int ret;
	/* Only the verified hardware; do not guess protocols on other models. */
	if (!dmi_match(DMI_PRODUCT_NAME, "Predator PHN16S-71") || !wmi_has_guid(GAMING_GUID)) return -ENODEV;
	INIT_DELAYED_WORK(&fan_watchdog, fan_watchdog_fn);
    INIT_WORK(&shortcut_notify_work, shortcut_notify_fn);
	pdev = platform_device_register_simple("preysense", -1, NULL, 0);
	if (IS_ERR(pdev)) return PTR_ERR(pdev);
	/* ERM4 is optional: CPU/fans still work if the signature is absent. */
	erm4_map();
	ret = sysfs_create_groups(&pdev->dev.kobj, preysense_groups);
	if (ret) {
		erm4_unmap();
		platform_device_unregister(pdev);
	} else {
        atomic64_set(&keyboard_activity_ns, ktime_get_boottime_ns());
        ret = input_register_handler(&preysense_keys);
        if (ret) {
		cancel_work_sync(&shortcut_notify_work);
		erm4_unmap();
		platform_device_unregister(pdev);
		return ret;
	}
        register_pm_notifier(&sleep_notifier);
    }
	return ret;
}
static void __exit preysense_exit(void)
{
	input_unregister_handler(&preysense_keys);
    cancel_work_sync(&shortcut_notify_work);
	unregister_pm_notifier(&sleep_notifier);
	cancel_delayed_work_sync(&fan_watchdog);
	restore_auto();
	erm4_unmap();
	platform_device_unregister(pdev);
}
module_init(preysense_init);
module_exit(preysense_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("PreySense PHN16S-71 limited Gaming WMI bridge");
