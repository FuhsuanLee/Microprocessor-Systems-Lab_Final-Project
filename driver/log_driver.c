#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/timekeeping.h>
#include <linux/device.h>

#define MODULE_NAME "log_driver"
#define LOG_BUF_SIZE 4096

static char log_buf[LOG_BUF_SIZE];
static size_t log_len;

static int major_num;
static struct class *log_class;
static struct device *log_device;

static char *log_devnode(struct device *dev, umode_t *mode)
{
    if (mode)
        *mode = 0666;  // 設定 /dev/log_driver 權限
    return NULL;
}

/* ===== 驅動 write ===== */
static ssize_t drv_write(struct file *filp, const char *buf, size_t count, loff_t *ppos)
{
    struct timespec64 ts;
    char user_buf[256];
    char log_entry[320];
    int entry_len;
    size_t space;

    if (count >= sizeof(user_buf))
        count = sizeof(user_buf) - 1;

    if (copy_from_user(user_buf, buf, count))
        return -EFAULT;

    user_buf[count] = '\0';

    ktime_get_real_ts64(&ts);

    entry_len = snprintf(
        log_entry,
        sizeof(log_entry),
        "[%lld.%06ld] %s\n",
        (long long)ts.tv_sec,
        ts.tv_nsec / 1000,
        user_buf
    );

    if (entry_len <= 0)
        return count;

    space = LOG_BUF_SIZE - log_len - 1;
    if (space == 0)
        return -ENOSPC;

    if (entry_len > space)
        entry_len = space;

    memcpy(log_buf + log_len, log_entry, entry_len);
    log_len += entry_len;
    log_buf[log_len] = '\0';

    printk(KERN_INFO "[demo_log] %s", log_entry);

    return count;
}

/* ===== 驅動 read ===== */
static ssize_t drv_read(struct file *filp, char *buf, size_t count, loff_t *ppos)
{
    if (*ppos >= log_len)
        return 0;

    if (count > log_len - *ppos)
        count = log_len - *ppos;

    if (copy_to_user(buf, log_buf + *ppos, count))
        return -EFAULT;

    *ppos += count;
    return count;
}

static int drv_open(struct inode *inode, struct file *filp)
{
    return 0;
}
static int drv_release(struct inode *inode, struct file *filp)
{
    return 0;
}
static long drv_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
    return 0;
}

static struct file_operations drv_fops = {
    .read = drv_read,
    .write = drv_write,
    .unlocked_ioctl = drv_ioctl,
    .open = drv_open,
    .release = drv_release,
};

/* ===== 模組初始化 ===== */
static int __init demo_init(void)
{
    major_num = register_chrdev(0, MODULE_NAME, &drv_fops); // major 0 表示自動分配
    if (major_num < 0) {
        printk(KERN_ERR "%s: can't register char device\n", MODULE_NAME);
        return major_num;
    }

    log_class = class_create(THIS_MODULE, MODULE_NAME);
    if (IS_ERR(log_class)) {
        unregister_chrdev(major_num, MODULE_NAME);
        return PTR_ERR(log_class);
    }

    log_class->devnode = log_devnode;  // 指定 devnode callback

    log_device = device_create(log_class, NULL, MKDEV(major_num, 0), NULL, MODULE_NAME);
    if (IS_ERR(log_device)) {
        class_destroy(log_class);
        unregister_chrdev(major_num, MODULE_NAME);
        return PTR_ERR(log_device);
    }

    log_len = 0;
    printk(KERN_INFO "%s: started with major %d\n", MODULE_NAME, major_num);
    return 0;
}

/* ===== 模組移除 ===== */
static void __exit demo_exit(void)
{
    device_destroy(log_class, MKDEV(major_num, 0));
    class_destroy(log_class);
    unregister_chrdev(major_num, MODULE_NAME);
    printk(KERN_INFO "%s: removed\n", MODULE_NAME);
}

module_init(demo_init);
module_exit(demo_exit);

MODULE_LICENSE("GPL");