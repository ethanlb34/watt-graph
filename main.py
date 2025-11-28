import subprocess
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from threading import Thread
from queue import Queue, Empty
import shutil
import sys

# -------------------- Config --------------------
MAX_WATT = 200 # If your CPU has a higher TDP than 200W, change this to your CPU's TDP
SMOOTH_WINDOW = 5
HISTORY_LEN = 100
OUTPUT_FILE = 'pkgwatt.png'
UPDATE_INTERVAL = 100  # ms
# ----------------- End Config -------------------

def install():
    if shutil.which("turbostat") is not None:
        return
    print("turbostat not found, installing")
    if shutil.which("apt"):
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y", "linux-tools-common", "linux-tools-$(uname -r)"], check=True, shell=True)
    elif shutil.which("dnf"):
        subprocess.run(["sudo", "dnf", "install", "-y", "kernel-tools"], check=True)
    elif shutil.which("pacman"):
        subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "linux-tools"], check=True)
    else:
        print("Cannot detect package manager, please install turbostat manually")
        sys.exit(1)

install()

pkg_watt_history = []
pkg_watt_all = []
data_queue = Queue()

plt.style.use('dark_background')
fig, ax = plt.subplots()
line1, = ax.plot([], [], label='PkgWatt', color='red')
ax.set_xlim(0, HISTORY_LEN)
ax.set_ylim(0, MAX_WATT)
ax.set_xlabel('Sample')
ax.set_ylabel('PkgWatt')
ax.set_title('Wattage')
ax.legend()
fig.tight_layout()

def smooth(data, window=SMOOTH_WINDOW):
    if len(data) < window:
        return data
    smoothed = []
    sum = 0
    for i, val in enumerate(data):
        sum += val
        if i >= window:
            sum -= data[i - window]
            smoothed.append(sum / window)
        else:
            smoothed.append(sum / (i + 1))
    return smoothed

def read_turbostat(queue: Queue):
    process = subprocess.Popen(
        ['sudo', 'turbostat', '--Summary', '--quiet', '--show', 'PkgWatt', '--interval', '1'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            value = float(line)
            queue.put(value)
        except ValueError:
            continue

Thread(target=read_turbostat, args=(data_queue,), daemon=True).start()

def update(frame):
    while True:
        try:
            value = data_queue.get_nowait()
            value = max(0, min(value, MAX_WATT))
            pkg_watt_history.append(value)
            pkg_watt_all.append(value)
        except Empty:
            break

    pkg_watt_history[:] = pkg_watt_history[-HISTORY_LEN:]
    smoothed_data = smooth(pkg_watt_history)
    line1.set_data(range(len(smoothed_data)), smoothed_data)
    ax.relim()
    ax.autoscale_view()
    return line1,

def on_close(event):
    smoothed_all = smooth(pkg_watt_all)
    plt.figure(figsize=(12,6))
    plt.plot(smoothed_all, color='red', label='PkgWatt')
    plt.xlabel('Sample')
    plt.ylabel('PkgWatt (W)')
    plt.title('CPU Power Summary (All Samples)')
    plt.ylim(0, MAX_WATT)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE)
    print(f"Saved full-session summary graph to {OUTPUT_FILE}")
    exit()

fig.canvas.mpl_connect('close_event', on_close)

ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL, blit=True)
plt.show()
