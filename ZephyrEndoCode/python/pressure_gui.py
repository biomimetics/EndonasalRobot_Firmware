"""
pressure_gui.py
GUI for the 12 pressure regulators (actuators) on the STM32 board.

Run:   python pressure_gui.py
Test with no hardware: run fake_board.py first, then connect to  socket://localhost:7777

Groups:  pick a group (one trial setup) from the dropdown at the top.
         Each group has its own psi per actuator, its own patterns and its own chains.
         Patterns marked "shared" show up in every group.
Left:    each actuator has a psi (for this group) and an ON/OFF button (sends right away).
         Untick 'use' for actuators that are unplugged or broken: they are always sent 0,
         and patterns skip them.
Middle:  patterns. A pattern says, for each actuator, ON / OFF / leave alone.
         An ON can have its own psi for that pattern; blank uses the actuator's psi.
         Each pattern has a Send button. Click them in any order.
Right:   chains. A list of patterns in order. Step through with "Send next"
         (or the Right arrow key). Optional auto mode moves on by itself.

Everything saves automatically to actuators.json next to this file.
Esc or VENT ALL turns every actuator off.

Sends the same serial commands as the original script (PWM1 ... PWM12),
so the STM32 firmware does not need to change.
"""

import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import serial
from serial.tools import list_ports

# ---------------- settings (same numbers as the original script) ----------------
N = 12
BAUD = 230400
DEFAULT_PORT = "/dev/ttyACM0"
HARD_MAX_PSI = 30          # the original script never allowed more than 30
DEFAULT_MAX_PSI = 15       # starting limit, change it in the top bar
DEFAULT_PSI = 10           # starting psi for each actuator
REGULATOR_FULL_SCALE = 67  # from pressureToPWM(): 5 V on the regulator = 67
SystemCoreClock = 16000000
PWM_FREQUENCY = 2000
PWM_PERIOD = ((SystemCoreClock / PWM_FREQUENCY) - 1) * 6

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(HERE, "actuators.json")
DATA_DIR = os.path.join(HERE, "data")

ON_BG, OFF_BG = "#2e7d32", "#d0d0d0"
CURRENT_BG = "#c8e6c9"
SHARED_FG = "#1565c0"
DISABLED_BG = "#9e9e9e"


def psi_to_pwm(psi):
    volts = psi / REGULATOR_FULL_SCALE * 5
    return volts / 3.3 * PWM_PERIOD


def build_lines(values):
    """Same format as makePressureCmdString(): 4 regulators per line."""
    lines = []
    for start in range(0, N, 4):
        line = b""
        for i in range(start, start + 4):
            line += ("PWM%d " % (i + 1)).encode() + ("%-6d" % psi_to_pwm(values[i])).encode()
        lines.append(line + b"\n")
    return lines


def fmt(x):
    return "%g" % round(x, 2)


def is_on(v):
    """Pattern value: "on", "off", or a number (= ON at that psi)."""
    return v == "on" or isinstance(v, (int, float))


def pattern_psi(v):
    """The psi a pattern value asks for, or None to use the actuator's own psi."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def new_group(psi=None):
    return {"psi": list(psi) if psi else [DEFAULT_PSI] * N, "patterns": {}, "chains": {}}


def renamed(d, old, new, new_value=None):
    """Return dict d with key old renamed to new, keeping its position."""
    return {(new if k == old else k): (new_value if (k == old and new_value is not None) else v)
            for k, v in d.items()}


# ---------------- serial link ----------------
class Link:
    """Owns the serial port. A background thread reads what the board sends back."""

    def __init__(self, log_q):
        self.ser = None
        self.log_q = log_q
        self.stop = threading.Event()
        self.rec_lock = threading.Lock()
        self.rec_file = None

    def connected(self):
        return self.ser is not None and self.ser.is_open

    def connect(self, port):
        # serial_for_url works for real ports (COM3, /dev/ttyACM0) and for
        # the fake board (socket://localhost:7777)
        if port.startswith("socket://"):
            self.ser = serial.serial_for_url(port, baudrate=BAUD, timeout=0.1)
        else:
            # exclusive: refuse to open if another program already has the port
            self.ser = serial.Serial(port, BAUD, timeout=0.1, exclusive=True)
        self.ser.reset_input_buffer()
        self.stop.clear()
        threading.Thread(target=self._reader, args=(self.ser,), daemon=True).start()

    def _reader(self, ser):
        errors = 0
        while not self.stop.is_set():
            try:
                raw = ser.readline()
                errors = 0
            except Exception as e:
                if self.stop.is_set():
                    break
                errors += 1
                if errors == 1:
                    self.log_q.put("serial read error: %s" % e)
                if errors >= 50:
                    self.log_q.put("serial keeps failing: is another program using this port, "
                                   "or is the board unplugged? Disconnect and reconnect.")
                    break
                time.sleep(0.1)
                continue
            if not raw:
                continue
            text = raw.decode("ascii", errors="replace").strip()
            with self.rec_lock:
                if self.rec_file:
                    self.rec_file.write(text + "\n")
            # only show messages from the board, not the constant sensor stream
            if text.startswith("#") or text.startswith("***"):
                self.log_q.put("board: " + text)

    def send_lines(self, lines):
        for line in lines:
            self.ser.write(line)
            time.sleep(0.002)

    def start_record(self, path):
        with self.rec_lock:
            self.rec_file = open(path, "w")
            self.rec_file.write("time, hx711, qdec3, qdec5, adc8, adc9, adc10, adc11, adc12, adc13, adc14, adc15\n")

    def stop_record(self):
        with self.rec_lock:
            if self.rec_file:
                self.rec_file.close()
                self.rec_file = None

    def close(self):
        self.stop.set()
        time.sleep(0.2)
        self.stop_record()
        try:
            self.ser.close()
        except Exception:
            pass
        self.ser = None


# ---------------- small helpers ----------------
class ScrollFrame(ttk.Frame):
    """A frame with a vertical scrollbar. Put widgets in .inner"""

    def __init__(self, parent, height=300):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")


class PatternEditor(tk.Toplevel):
    """Popup to make or edit a pattern: for each actuator pick leave / ON / OFF."""

    def __init__(self, app, title, name="", spec=None, shared=False):
        super().__init__(app.root)
        self.app = app
        self.result = None
        self.title(title)
        self.transient(app.root)
        spec = spec or {}

        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Name:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value=name)
        e = ttk.Entry(f, textvariable=self.name_var, width=26)
        e.grid(row=0, column=1, columnspan=4, sticky="w")
        self.shared_var = tk.BooleanVar(value=shared)
        ttk.Checkbutton(f, text="Shared (shows in every group)", variable=self.shared_var
                        ).grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(f, text="For each actuator: leave it alone, turn it ON, or turn it OFF.\n"
                          "psi: only for ON. Leave blank to use the actuator's normal psi.",
                  foreground="gray", justify="left").grid(row=2, column=0, columnspan=7, sticky="w", pady=(8, 4))
        for c, t in enumerate(("leave", "ON", "OFF", "psi", "")):
            ttk.Label(f, text=t).grid(row=3, column=2 + c, padx=8)

        self.choice, self.psi_txt = [], []
        for i in range(N):
            val = spec.get(str(i + 1), "leave")
            pp = pattern_psi(val)
            v = tk.StringVar(value="on" if is_on(val) else val)
            pv = tk.StringVar(value=fmt(pp) if pp is not None else "")
            self.psi_txt.append(pv)
            ttk.Label(f, text=str(i + 1)).grid(row=4 + i, column=0, sticky="e")
            unused = not app.is_enabled(i)
            ttk.Label(f, text=app.names[i].get() + ("  (unused)" if unused else ""),
                      foreground="gray" if unused else "").grid(row=4 + i, column=1, sticky="w", padx=6)
            for c, val in enumerate(("leave", "on", "off")):
                ttk.Radiobutton(f, variable=v, value=val).grid(row=4 + i, column=2 + c)
            ttk.Entry(f, textvariable=pv, width=6).grid(row=4 + i, column=5, padx=4)
            ttk.Label(f, text="normal %s" % fmt(app.psi_value(i)), foreground="gray"
                      ).grid(row=4 + i, column=6, sticky="w")
            self.choice.append(v)

        b = ttk.Frame(f)
        b.grid(row=4 + N, column=0, columnspan=7, pady=(10, 0), sticky="ew")
        ttk.Button(b, text="Copy current ON/OFF", command=self.copy_current).pack(side="left")
        ttk.Button(b, text="All leave", command=lambda: [v.set("leave") for v in self.choice]).pack(side="left", padx=4)
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Save", command=self.save).pack(side="right", padx=4)

        self.bind("<Escape>", lambda ev: self.destroy())
        self.grab_set()
        e.focus_set()

    def copy_current(self):
        for i, v in enumerate(self.choice):
            if not self.app.is_enabled(i):
                v.set("leave")
                self.psi_txt[i].set("")
            else:
                v.set("on" if self.app.on[i] else "off")
                ov = self.app.override[i] if self.app.on[i] else None
                self.psi_txt[i].set(fmt(ov) if ov is not None else "")

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Pattern", "Give the pattern a name.", parent=self)
            return
        spec = {}
        mx = self.app.max_psi()
        for i, v in enumerate(self.choice):
            c = v.get()
            if c == "leave":
                continue
            txt = self.psi_txt[i].get().strip()
            if c == "on" and txt:
                try:
                    x = float(txt)
                except ValueError:
                    messagebox.showwarning("Pattern", "psi for %s isn't a number: '%s'"
                                           % (self.app.names[i].get(), txt), parent=self)
                    return
                if x < 0 or x > mx:
                    messagebox.showwarning("Pattern", "psi for %s must be between 0 and the max (%s)."
                                           % (self.app.names[i].get(), fmt(mx)), parent=self)
                    return
                spec[str(i + 1)] = x
            else:
                spec[str(i + 1)] = c
        if not spec:
            messagebox.showwarning("Pattern", "Set at least one actuator to ON or OFF.", parent=self)
            return
        self.result = (name, spec, self.shared_var.get())
        self.destroy()


class PickGroup(tk.Toplevel):
    """Popup to choose a group to copy a pattern into."""

    def __init__(self, app, groups, pattern):
        super().__init__(app.root)
        self.result = None
        self.title("Copy to group")
        self.transient(app.root)
        f = ttk.Frame(self, padding=10)
        f.pack()
        ttk.Label(f, text="Copy '%s' into group:" % pattern).pack(anchor="w")
        self.var = tk.StringVar(value=groups[0])
        ttk.Combobox(f, textvariable=self.var, values=groups, state="readonly", width=24).pack(pady=6)
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Copy", command=self.ok).pack(side="right", padx=4)
        self.grab_set()

    def ok(self):
        self.result = self.var.get()
        self.destroy()


# ---------------- main window ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Actuator Control")

        self.log_q = queue.Queue()
        self.link = Link(self.log_q)
        self.data = self.load_data()

        self.group_var = tk.StringVar(value=self.data["current_group"])
        self.names = [tk.StringVar(value=n) for n in self.data["names"]]
        self.psi = [tk.StringVar(value=fmt(p)) for p in self.g()["psi"]]
        self.enabled = [tk.BooleanVar(value=e) for e in self.data["enabled"]]
        self.on = [False] * N
        self.override = [None] * N   # psi set by the last pattern, None = use the psi box

        self.max_var = tk.StringVar(value=str(DEFAULT_MAX_PSI))
        self.record = tk.BooleanVar(value=False)
        self.chain_var = tk.StringVar()
        self.add_var = tk.StringVar()
        self.auto = tk.BooleanVar(value=False)
        self.auto_secs = tk.StringVar(value="2")
        self.end_off = tk.BooleanVar(value=False)

        self.run_chain = None   # name of chain being stepped through
        self.pos = None         # current step in that chain (None = not running)
        self.auto_job = None

        self.build_top()
        self.build_group_bar()
        self.build_actuators()
        self.build_patterns()
        self.build_chains()
        self.build_log()

        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(2, weight=1)
        root.bind("<Escape>", lambda e: self.vent_all())
        root.bind("<Right>", lambda e: self.key_step(1))
        root.bind("<Left>", lambda e: self.key_step(-1))
        root.bind_all("<MouseWheel>", self.on_wheel)
        root.bind_all("<Button-4>", self.on_wheel)
        root.bind_all("<Button-5>", self.on_wheel)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.refresh_ports()
        self.refresh_group_box()
        self.refresh_patterns()
        self.refresh_chain_box()
        self.poll_log()
        self.log("Not connected: commands are only shown here until you press Connect.")

    # ----- saving / loading -----
    def load_data(self):
        data = {}
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE) as f:
                    data = json.load(f)
            except Exception as e:
                messagebox.showwarning("actuators.json", "Could not read actuators.json:\n%s" % e)

        if "groups" not in data:
            # first run, or a file from the version without groups: put it all in "Group 1"
            acts = data.get("actuators", [])
            names = [acts[i].get("name", "Act %d" % (i + 1)) if i < len(acts) else "Act %d" % (i + 1)
                     for i in range(N)]
            psi = [float(acts[i].get("psi", DEFAULT_PSI)) if i < len(acts) else DEFAULT_PSI for i in range(N)]
            g = new_group(psi)
            g["patterns"] = data.get("patterns", {})
            g["chains"] = data.get("chains", {})
            data = {"names": names, "shared_patterns": {}, "groups": {"Group 1": g},
                    "current_group": "Group 1"}

        names = data.get("names", [])
        data["names"] = [names[i] if i < len(names) else "Act %d" % (i + 1) for i in range(N)]
        data.setdefault("shared_patterns", {})
        en = data.get("enabled", [])
        data["enabled"] = [bool(en[i]) if i < len(en) else True for i in range(N)]
        if not data["groups"]:
            data["groups"] = {"Group 1": new_group()}
        for g in data["groups"].values():
            psi = g.get("psi", [])
            g["psi"] = [float(psi[i]) if i < len(psi) else DEFAULT_PSI for i in range(N)]
            g.setdefault("patterns", {})
            g.setdefault("chains", {})
        if data.get("current_group") not in data["groups"]:
            data["current_group"] = next(iter(data["groups"]))
        return data

    def save_data(self):
        self.data["names"] = [n.get() for n in self.names]
        self.data["enabled"] = [v.get() for v in self.enabled]
        self.g()["psi"] = [self.psi_value(i) for i in range(N)]
        self.data["current_group"] = self.group_var.get()
        tmp = SAVE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=1)
        os.replace(tmp, SAVE_FILE)

    # ----- groups -----
    def g(self, name=None):
        """The current group (or the named one)."""
        if name is None:
            name = self.group_var.get() if hasattr(self, "group_var") else self.data["current_group"]
        return self.data["groups"][name]

    def build_group_bar(self):
        f = ttk.Frame(self.root, padding=(6, 0, 6, 4))
        f.grid(row=1, column=0, columnspan=3, sticky="ew")
        ttk.Label(f, text="Group (trial):", font=("TkDefaultFont", 11, "bold")).pack(side="left")
        self.group_box = ttk.Combobox(f, textvariable=self.group_var, state="readonly", width=24,
                                      font=("TkDefaultFont", 11))
        self.group_box.pack(side="left", padx=6)
        self.group_box.bind("<<ComboboxSelected>>", lambda e: self.switch_group())
        ttk.Button(f, text="New", command=self.new_group).pack(side="left", padx=2)
        ttk.Button(f, text="Duplicate", command=self.duplicate_group).pack(side="left", padx=2)
        ttk.Button(f, text="Rename", command=self.rename_group).pack(side="left", padx=2)
        ttk.Button(f, text="Delete", command=self.delete_group).pack(side="left", padx=2)
        ttk.Label(f, text="each group has its own psi, patterns and chains; shared patterns show in all",
                  foreground="gray").pack(side="left", padx=10)

    def refresh_group_box(self):
        self.group_box["values"] = list(self.data["groups"])

    def load_group_into_view(self):
        for i, p in enumerate(self.g()["psi"]):
            self.psi[i].set(fmt(p))
        self.chain_var.set("")
        self.refresh_patterns()
        self.refresh_chain_box()

    def switch_group(self):
        new = self.group_var.get()
        old = self.data["current_group"]
        if new == old:
            return
        # save the psi boxes into the group we're leaving
        self.data["groups"][old]["psi"] = [self.psi_value(i) for i in range(N)]
        self.stop_chain(quiet=True)
        self.load_group_into_view()
        self.save_data()
        self.log("switched to group '%s'" % new)
        if any(self.on):
            self.send_state("group '%s' psi applied" % new)

    def ask_group_name(self, title, initial=""):
        name = simpledialog.askstring(title, "Group name:", initialvalue=initial, parent=self.root)
        if not name or not name.strip():
            return None
        name = name.strip()
        if name in self.data["groups"]:
            messagebox.showwarning(title, "A group called '%s' already exists." % name)
            return None
        return name

    def new_group(self):
        name = self.ask_group_name("New group")
        if not name:
            return
        self.save_data()
        self.data["groups"][name] = new_group([self.psi_value(i) for i in range(N)])
        self.refresh_group_box()
        self.group_var.set(name)
        self.switch_group()

    def duplicate_group(self):
        old = self.group_var.get()
        name = self.ask_group_name("Duplicate group", old + " copy")
        if not name:
            return
        self.save_data()
        self.data["groups"][name] = json.loads(json.dumps(self.g(old)))
        self.refresh_group_box()
        self.group_var.set(name)
        self.switch_group()

    def rename_group(self):
        old = self.group_var.get()
        name = self.ask_group_name("Rename group", old)
        if not name:
            return
        self.save_data()
        self.data["groups"] = renamed(self.data["groups"], old, name)
        self.data["current_group"] = name
        self.group_var.set(name)
        self.refresh_group_box()
        self.save_data()

    def delete_group(self):
        name = self.group_var.get()
        if len(self.data["groups"]) == 1:
            messagebox.showinfo("Delete", "You need at least one group.")
            return
        if not messagebox.askyesno("Delete", "Delete group '%s' with its patterns and chains?\n"
                                             "(shared patterns are kept)" % name):
            return
        self.stop_chain(quiet=True)
        del self.data["groups"][name]
        first = next(iter(self.data["groups"]))
        self.data["current_group"] = first
        self.group_var.set(first)
        self.refresh_group_box()
        self.load_group_into_view()
        self.save_data()
        self.log("deleted group '%s', now on '%s'" % (name, first))

    # ----- top bar -----
    def build_top(self):
        f = ttk.Frame(self.root, padding=6)
        f.grid(row=0, column=0, columnspan=3, sticky="ew")

        ttk.Label(f, text="Port:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(f, textvariable=self.port_var, width=24)
        self.port_box.pack(side="left", padx=4)
        ttk.Button(f, text="Refresh", command=self.refresh_ports).pack(side="left")
        self.connect_btn = ttk.Button(f, text="Connect", command=self.toggle_connect)
        self.connect_btn.pack(side="left", padx=4)
        self.status = ttk.Label(f, text="not connected", foreground="gray")
        self.status.pack(side="left", padx=8)

        tk.Button(f, text="VENT ALL (Esc)", bg="#c62828", fg="white",
                  font=("TkDefaultFont", 11, "bold"), command=self.vent_all).pack(side="right")
        ttk.Checkbutton(f, text="Record sensor data", variable=self.record,
                        command=self.toggle_record).pack(side="right", padx=8)
        mx = ttk.Spinbox(f, textvariable=self.max_var, from_=1, to=HARD_MAX_PSI, increment=1,
                         width=5, command=self.apply_max)
        mx.pack(side="right")
        mx.bind("<Return>", lambda e: self.apply_max())
        mx.bind("<FocusOut>", lambda e: self.apply_max())
        ttk.Label(f, text="Max psi:").pack(side="right", padx=(8, 2))

    def refresh_ports(self):
        found = list_ports.comports()
        ports = [p.device for p in found] + ["socket://localhost:7777"]
        self.port_box["values"] = ports
        # tell the user what each USB port is, and prefer the STM32 board
        stm = []
        for p in found:
            desc = "%s %s" % (p.description or "", p.manufacturer or "")
            if "ACM" in p.device or "USB" in p.device or p.device.startswith("COM"):
                if hasattr(self, "log_box"):
                    self.log("port %s: %s" % (p.device, (p.description or "?")))
            if "STM" in desc.upper() or "ST-LINK" in desc.upper():
                stm.append(p.device)
        if stm:
            self.port_var.set(stm[0])
        elif not self.port_var.get():
            usb = [p for p in ports if "ACM" in p or "USB" in p or p.startswith("COM")]
            self.port_var.set(usb[0] if usb else ports[0])

    def toggle_connect(self):
        if self.link.connected():
            self.stop_chain()
            self.all_off_quiet()
            self.send_state("all off before disconnect")
            self.record.set(False)
            self.link.close()
            self.status.config(text="not connected", foreground="gray")
            self.connect_btn.config(text="Connect")
            self.log("Disconnected.")
            return
        port = self.port_var.get().strip()
        try:
            self.link.connect(port)
        except Exception as e:
            messagebox.showerror("Connect", "Could not open %s:\n%s" % (port, e))
            return
        self.status.config(text="connected to " + port, foreground="green")
        self.connect_btn.config(text="Disconnect")
        self.log("Connected to %s. The board should answer '# parse_cmd ...' below." % port)
        self.link.send_lines([b"foo\n"])
        self.all_off_quiet()
        self.send_state("start: all off")

    def toggle_record(self):
        if self.record.get():
            if not self.link.connected():
                self.record.set(False)
                self.log("Connect first to record data.")
                return
            os.makedirs(DATA_DIR, exist_ok=True)
            path = os.path.join(DATA_DIR, time.strftime("data_%Y%m%d_%H%M%S.txt"))
            self.link.start_record(path)
            self.log("Recording to " + path)
        else:
            self.link.stop_record()
            self.log("Recording stopped.")

    def max_psi(self):
        try:
            m = float(self.max_var.get())
        except ValueError:
            m = DEFAULT_MAX_PSI
        return min(max(m, 1.0), HARD_MAX_PSI)

    def apply_max(self):
        m = self.max_psi()
        self.max_var.set(fmt(m))
        for sp in self.psi_spins:
            sp.config(to=m)
        for i in range(N):
            self.psi_value(i)  # clamps the boxes to the new max
        self.save_data()

    # ----- actuators panel -----
    def build_actuators(self):
        f = ttk.LabelFrame(self.root, text="Actuators", padding=6)
        f.grid(row=2, column=0, sticky="nsew", padx=6)
        for c, t in enumerate(("#", "name", "psi", "", "use")):
            ttk.Label(f, text=t, foreground="gray").grid(row=0, column=c)
        self.psi_spins, self.toggle_btns = [], []
        for i in range(N):
            r = i + 1
            ttk.Label(f, text=str(i + 1)).grid(row=r, column=0, sticky="e")
            name = ttk.Entry(f, textvariable=self.names[i], width=12)
            name.grid(row=r, column=1, padx=3, pady=1)
            name.bind("<FocusOut>", lambda e: self.names_changed())
            name.bind("<Return>", lambda e: self.names_changed())
            sp = ttk.Spinbox(f, textvariable=self.psi[i], from_=0, to=self.max_psi(), increment=0.5,
                             width=6, command=lambda i=i: self.psi_changed(i))
            sp.grid(row=r, column=2, padx=3)
            sp.bind("<Return>", lambda e, i=i: self.psi_changed(i))
            sp.bind("<FocusOut>", lambda e, i=i: self.psi_changed(i, quiet=True))
            self.psi_spins.append(sp)
            b = tk.Button(f, text="OFF", width=7, command=lambda i=i: self.toggle(i))
            b.grid(row=r, column=3, padx=3, pady=1)
            self.toggle_btns.append(b)
            ttk.Checkbutton(f, variable=self.enabled[i],
                            command=lambda i=i: self.enable_changed(i)).grid(row=r, column=4)
            self.update_toggle(i)
        ttk.Label(f, text="psi = pressure used when ON (saved per group)\nuse = untick if unplugged/broken (always sent 0)",
                  foreground="gray").grid(row=N + 1, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Button(f, text="Re-send current state", command=lambda: self.send_state("re-send")
                   ).grid(row=N + 2, column=0, columnspan=5, sticky="w", pady=(4, 0))

    def psi_value(self, i):
        try:
            x = float(self.psi[i].get())
        except ValueError:
            x = DEFAULT_PSI
        x = min(max(x, 0.0), self.max_psi())
        if self.psi[i].get() != fmt(x):
            self.psi[i].set(fmt(x))
        return x

    def psi_changed(self, i, quiet=False):
        before = self.g()["psi"][i]
        x = self.psi_value(i)
        self.save_data()
        if self.on[i] and (x != before or not quiet):
            self.override[i] = None   # typing a psi takes over from the pattern's psi
            self.update_toggle(i)
            self.send_state("%s psi -> %s" % (self.names[i].get(), fmt(x)))

    def names_changed(self):
        self.save_data()
        self.refresh_patterns()

    def is_enabled(self, i):
        return self.enabled[i].get()

    def update_toggle(self, i):
        if not self.is_enabled(i):
            self.on[i] = False
            self.toggle_btns[i].config(text="unused", bg=DISABLED_BG, fg="white", state="disabled",
                                       disabledforeground="white",
                                       activebackground=DISABLED_BG)
            self.psi_spins[i].config(state="disabled")
            return
        on = self.on[i]
        if not on:
            self.override[i] = None
        label = "OFF"
        if on:
            label = "ON" if self.override[i] is None else "ON %s" % fmt(self.eff_psi(i))
        self.toggle_btns[i].config(text=label, bg=ON_BG if on else OFF_BG,
                                   fg="white" if on else "black", state="normal",
                                   activebackground=ON_BG if on else OFF_BG)
        self.psi_spins[i].config(state="normal")

    def enable_changed(self, i):
        was_on = self.on[i]
        self.update_toggle(i)
        self.save_data()
        self.refresh_patterns()
        name = self.names[i].get()
        if self.is_enabled(i):
            self.log("%s back in use" % name)
        elif was_on:
            self.send_state("%s set unused (turned off)" % name)
        else:
            self.log("%s set unused: it will always get 0 and patterns skip it" % name)

    def toggle(self, i):
        if not self.is_enabled(i):
            return
        self.on[i] = not self.on[i]
        self.override[i] = None
        self.update_toggle(i)
        self.send_state("%s %s" % (self.names[i].get(), "ON" if self.on[i] else "OFF"))

    def eff_psi(self, i):
        """psi actually sent when ON: the pattern's psi if it set one, else the psi box."""
        if self.override[i] is not None:
            return min(max(self.override[i], 0.0), self.max_psi())
        return self.psi_value(i)

    def all_off_quiet(self):
        self.on = [False] * N
        self.override = [None] * N
        for i in range(N):
            self.update_toggle(i)

    def on_desc(self):
        parts = ["%s %s" % (self.names[i].get(), fmt(self.eff_psi(i))) for i in range(N)
                 if self.on[i] and self.is_enabled(i)]
        return ", ".join(parts) if parts else "nothing on"

    def send_state(self, note):
        values = [self.eff_psi(i) if (self.on[i] and self.is_enabled(i)) else 0.0 for i in range(N)]
        msg = "%s   |  now on: %s" % (note, self.on_desc())
        if self.link.connected():
            try:
                self.link.send_lines(build_lines(values))
                self.log("sent: " + msg)
            except Exception as e:
                self.log("send failed: %s" % e)
        else:
            self.log("(not connected) " + msg)

    def vent_all(self):
        self.stop_chain(quiet=True)
        self.all_off_quiet()
        self.send_state("VENT ALL")

    # ----- patterns panel -----
    def build_patterns(self):
        f = ttk.LabelFrame(self.root, text="Patterns  (click Send in any order)", padding=6)
        f.grid(row=2, column=1, sticky="nsew", padx=6)
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 4))
        ttk.Button(top, text="New pattern", command=self.new_pattern).pack(side="left")
        ttk.Button(top, text="New from current ON/OFF",
                   command=lambda: self.new_pattern(from_current=True)).pack(side="left", padx=4)
        self.pat_sf = ScrollFrame(f, height=420)
        self.pat_sf.pack(fill="both", expand=True)

    def find_pattern(self, name):
        """Look in this group first, then the shared ones. Returns (spec, shared) or (None, None)."""
        if name in self.g()["patterns"]:
            return self.g()["patterns"][name], False
        if name in self.data["shared_patterns"]:
            return self.data["shared_patterns"][name], True
        return None, None

    def available_patterns(self):
        return list(self.g()["patterns"]) + [n for n in self.data["shared_patterns"]
                                              if n not in self.g()["patterns"]]

    def pattern_desc(self, spec):
        def label(k, v=None):
            i = int(k) - 1
            pp = pattern_psi(v)
            return (self.names[i].get() + (" @%s" % fmt(pp) if pp is not None else "")
                    + ("" if self.is_enabled(i) else " (unused)"))
        on = [label(k, v) for k, v in spec.items() if is_on(v)]
        off = [label(k) for k, v in spec.items() if v == "off"]
        parts = []
        if on:
            parts.append("ON: " + ", ".join(on))
        if off:
            parts.append("OFF: " + ", ".join(off))
        return "\n".join(parts)

    def pattern_row(self, inner, name, spec, shared):
        row = ttk.Frame(inner, padding=(0, 3))
        row.pack(fill="x")
        tk.Button(row, text="Send", bg=ON_BG, fg="white", width=6,
                  command=lambda: self.apply_pattern(name)).grid(row=0, column=0, rowspan=2, padx=(0, 6))
        title = ttk.Frame(row)
        title.grid(row=0, column=1, sticky="w")
        ttk.Label(title, text=name, font=("TkDefaultFont", 10, "bold")).pack(side="left")
        if shared:
            ttk.Label(title, text="  shared", foreground=SHARED_FG).pack(side="left")
        ttk.Label(row, text=self.pattern_desc(spec), foreground="gray",
                  wraplength=330, justify="left").grid(row=1, column=1, columnspan=2, sticky="w")
        btns = ttk.Frame(row)
        btns.grid(row=0, column=2, sticky="e")
        ttk.Button(btns, text="Edit", width=5, command=lambda: self.edit_pattern(name, shared)).pack(side="left", padx=1)
        if not shared:
            ttk.Button(btns, text="Copy to...", width=9,
                       command=lambda: self.copy_to_group(name)).pack(side="left", padx=1)
        ttk.Button(btns, text="Delete", width=6, command=lambda: self.delete_pattern(name, shared)).pack(side="left", padx=1)
        row.columnconfigure(1, weight=1)
        ttk.Separator(inner).pack(fill="x")

    def refresh_patterns(self):
        inner = self.pat_sf.inner
        for w in inner.winfo_children():
            w.destroy()
        own = self.g()["patterns"]
        shared = {n: s for n, s in self.data["shared_patterns"].items() if n not in own}

        ttk.Label(inner, text="This group (%s)" % self.group_var.get(),
                  font=("TkDefaultFont", 10, "underline")).pack(anchor="w", pady=(2, 2))
        if not own:
            ttk.Label(inner, text="none yet. Press 'New pattern'.", foreground="gray").pack(anchor="w", pady=(0, 6))
        for name, spec in own.items():
            self.pattern_row(inner, name, spec, False)

        ttk.Label(inner, text="Shared (every group)", foreground=SHARED_FG,
                  font=("TkDefaultFont", 10, "underline")).pack(anchor="w", pady=(10, 2))
        if not shared:
            ttk.Label(inner, text="none yet. Tick 'Shared' when making a pattern.",
                      foreground="gray").pack(anchor="w")
        for name, spec in shared.items():
            self.pattern_row(inner, name, spec, True)

        avail = self.available_patterns()
        self.add_box["values"] = avail
        if self.add_var.get() not in avail:
            self.add_var.set(avail[0] if avail else "")
        self.refresh_chain()

    def apply_pattern(self, name, note=None):
        spec, _ = self.find_pattern(name)
        if spec is None:
            self.log("pattern '%s' isn't in this group or shared, skipped" % name)
            return
        skipped = []
        for k, v in spec.items():
            i = int(k) - 1
            if not self.is_enabled(i):
                if is_on(v):
                    skipped.append(self.names[i].get())
                continue
            self.on[i] = is_on(v)
            self.override[i] = pattern_psi(v) if self.on[i] else None
        for i in range(N):
            self.update_toggle(i)
        note = note or "pattern '%s'" % name
        if skipped:
            note += "  (skipped unused: %s)" % ", ".join(skipped)
        self.send_state(note)

    def open_editor(self, title, name="", spec=None, shared=False):
        ed = PatternEditor(self, title, name, spec, shared)
        self.root.wait_window(ed)
        return ed.result

    def name_clash(self, name, shared, ignore=None):
        """Is this name already used somewhere it would collide? ignore = (name, shared) being edited."""
        def taken(where_name, where_shared):
            return ignore != (where_name, where_shared)
        if name in self.data["shared_patterns"] and taken(name, True):
            return "a shared pattern"
        if name in self.g()["patterns"] and taken(name, False):
            return "a pattern in this group"
        if shared:
            for gname, g in self.data["groups"].items():
                if name in g["patterns"] and (gname != self.group_var.get() or taken(name, False)):
                    return "a pattern in group '%s'" % gname
        return None

    def new_pattern(self, from_current=False):
        spec = {}
        if from_current:
            for i in range(N):
                if self.is_enabled(i):
                    if self.on[i] and self.override[i] is not None:
                        spec[str(i + 1)] = self.override[i]
                    else:
                        spec[str(i + 1)] = "on" if self.on[i] else "off"
        res = self.open_editor("New pattern", "", spec)
        if not res:
            return
        name, spec, shared = res
        clash = self.name_clash(name, shared)
        if clash:
            messagebox.showwarning("Pattern", "'%s' is already %s. Pick another name." % (name, clash))
            return
        (self.data["shared_patterns"] if shared else self.g()["patterns"])[name] = spec
        self.save_data()
        self.refresh_patterns()

    def edit_pattern(self, old, old_shared):
        spec, _ = self.find_pattern(old)
        res = self.open_editor("Edit pattern", old, spec, old_shared)
        if not res:
            return
        name, spec, shared = res
        clash = self.name_clash(name, shared, ignore=(old, old_shared))
        if clash:
            messagebox.showwarning("Pattern", "'%s' is already %s. Pick another name." % (name, clash))
            return
        old_store = self.data["shared_patterns"] if old_shared else self.g()["patterns"]
        new_store = self.data["shared_patterns"] if shared else self.g()["patterns"]
        if old_store is new_store:
            new_dict = renamed(old_store, old, name, spec)
            if shared:
                self.data["shared_patterns"] = new_dict
            else:
                self.g()["patterns"] = new_dict
        else:
            del old_store[old]
            new_store[name] = spec
            if old_shared and not shared:
                self.log("'%s' is now only in group '%s'" % (name, self.group_var.get()))
        if name != old:
            groups = self.data["groups"].values() if old_shared else [self.g()]
            for g in groups:
                for steps in g["chains"].values():
                    for j, s in enumerate(steps):
                        if s == old:
                            steps[j] = name
        self.save_data()
        self.refresh_patterns()

    def copy_to_group(self, name):
        others = [g for g in self.data["groups"] if g != self.group_var.get()]
        if not others:
            messagebox.showinfo("Copy", "Make another group first.")
            return
        dlg = PickGroup(self, others, name)
        self.root.wait_window(dlg)
        target = dlg.result
        if not target:
            return
        new_name = name
        tg = self.data["groups"][target]
        while new_name in tg["patterns"] or new_name in self.data["shared_patterns"]:
            new_name = simpledialog.askstring("Copy", "'%s' already exists there. New name:" % new_name,
                                              initialvalue=new_name + " copy", parent=self.root)
            if not new_name:
                return
            new_name = new_name.strip()
        tg["patterns"][new_name] = json.loads(json.dumps(self.g()["patterns"][name]))
        self.save_data()
        self.log("copied '%s' to group '%s'" % (name, target))

    def delete_pattern(self, name, shared):
        where = "every group" if shared else "this group"
        if messagebox.askyesno("Delete", "Delete pattern '%s' from %s?" % (name, where)):
            del (self.data["shared_patterns"] if shared else self.g()["patterns"])[name]
            self.save_data()
            self.refresh_patterns()

    def on_wheel(self, e):
        # scroll the pattern list when the mouse is over it
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            # mouse is over a dropdown list, which Tk can't look up; ignore
            return
        if w is None or not str(w).startswith(str(self.pat_sf)):
            return
        if e.num == 4:
            step = -1
        elif e.num == 5:
            step = 1
        else:
            step = -1 if e.delta > 0 else 1
        self.pat_sf.canvas.yview_scroll(step, "units")

    # ----- chains panel -----
    def build_chains(self):
        f = ttk.LabelFrame(self.root, text="Chains  (patterns in order)", padding=6)
        f.grid(row=2, column=2, sticky="nsew", padx=6)

        top = ttk.Frame(f)
        top.pack(fill="x")
        self.chain_box = ttk.Combobox(top, textvariable=self.chain_var, state="readonly", width=16)
        self.chain_box.pack(side="left")
        self.chain_box.bind("<<ComboboxSelected>>", lambda e: self.chain_selected())
        ttk.Button(top, text="New", width=5, command=self.new_chain).pack(side="left", padx=2)
        ttk.Button(top, text="Rename", width=7, command=self.rename_chain).pack(side="left", padx=2)
        ttk.Button(top, text="Delete", width=6, command=self.delete_chain).pack(side="left")

        self.chain_list = tk.Listbox(f, width=30, height=12, exportselection=False)
        self.chain_list.pack(fill="both", expand=True, pady=4)
        self.chain_list.bind("<Double-Button-1>", lambda e: self.jump_to_selected())

        a = ttk.Frame(f)
        a.pack(fill="x")
        self.add_box = ttk.Combobox(a, textvariable=self.add_var, state="readonly", width=16)
        self.add_box.pack(side="left")
        ttk.Button(a, text="Add to chain", command=self.chain_add).pack(side="left", padx=4)

        b = ttk.Frame(f)
        b.pack(fill="x", pady=4)
        ttk.Button(b, text="Up", width=4, command=lambda: self.chain_move(-1)).pack(side="left")
        ttk.Button(b, text="Down", width=5, command=lambda: self.chain_move(1)).pack(side="left", padx=2)
        ttk.Button(b, text="Remove", command=self.chain_remove).pack(side="left")

        ttk.Separator(f).pack(fill="x", pady=6)
        r = ttk.Frame(f)
        r.pack(fill="x")
        ttk.Button(r, text="< Back", command=lambda: self.chain_step(-1)).pack(side="left")
        tk.Button(r, text="Send next >", bg=ON_BG, fg="white", font=("TkDefaultFont", 11, "bold"),
                  command=lambda: self.chain_step(1)).pack(side="left", padx=4)
        tk.Button(r, text="Stop", bg="#ef6c00", fg="white", command=self.stop_chain).pack(side="left")

        au = ttk.Frame(f)
        au.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(au, text="Auto: next every", variable=self.auto, command=self.auto_changed).pack(side="left")
        ttk.Spinbox(au, textvariable=self.auto_secs, from_=0.2, to=60, increment=0.5, width=5).pack(side="left", padx=3)
        ttk.Label(au, text="s").pack(side="left")
        ttk.Checkbutton(f, text="All OFF when the chain ends", variable=self.end_off).pack(anchor="w")

        self.chain_status = ttk.Label(f, text="Press 'Send next' to start the chain. Double-click a step to jump to it.",
                                      foreground="gray", wraplength=260, justify="left")
        self.chain_status.pack(anchor="w", pady=(6, 0))

    def chain(self):
        return self.g()["chains"].get(self.chain_var.get())

    def refresh_chain_box(self, select=None):
        names = list(self.g()["chains"])
        self.chain_box["values"] = names
        if select:
            self.chain_var.set(select)
        elif self.chain_var.get() not in names:
            self.chain_var.set(names[0] if names else "")
        self.refresh_chain()

    def refresh_chain(self, select=None):
        if not hasattr(self, "chain_list"):
            return
        self.chain_list.delete(0, "end")
        for j, name in enumerate(self.chain() or []):
            missing = "" if self.find_pattern(name)[0] is not None else "  (missing)"
            self.chain_list.insert("end", "%d.  %s%s" % (j + 1, name, missing))
        if self.pos is not None and self.run_chain == self.chain_var.get() and self.pos < self.chain_list.size():
            self.chain_list.itemconfig(self.pos, background=CURRENT_BG)
            self.chain_list.see(self.pos)
        if select is not None and 0 <= select < self.chain_list.size():
            self.chain_list.selection_set(select)

    def chain_selected(self):
        if self.pos is not None and self.run_chain != self.chain_var.get():
            self.stop_chain()
        self.refresh_chain()

    def chain_sel(self):
        sel = self.chain_list.curselection()
        return sel[0] if sel else None

    def new_chain(self):
        name = simpledialog.askstring("New chain", "Chain name:", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.g()["chains"]:
            messagebox.showwarning("Chain", "'%s' already exists in this group." % name)
            return
        self.g()["chains"][name] = []
        self.save_data()
        self.refresh_chain_box(select=name)

    def rename_chain(self):
        old = self.chain_var.get()
        if not old:
            return
        name = simpledialog.askstring("Rename chain", "New name:", initialvalue=old, parent=self.root)
        if not name or not name.strip() or name.strip() == old:
            return
        name = name.strip()
        if name in self.g()["chains"]:
            messagebox.showwarning("Chain", "'%s' already exists in this group." % name)
            return
        self.g()["chains"] = renamed(self.g()["chains"], old, name)
        if self.run_chain == old:
            self.run_chain = name
        self.save_data()
        self.refresh_chain_box(select=name)

    def delete_chain(self):
        name = self.chain_var.get()
        if name and messagebox.askyesno("Delete", "Delete chain '%s'?" % name):
            if self.run_chain == name:
                self.stop_chain()
            del self.g()["chains"][name]
            self.save_data()
            self.refresh_chain_box()

    def chain_add(self):
        ch, pat = self.chain(), self.add_var.get()
        if ch is None:
            self.log("Make a chain first (New).")
            return
        if not pat:
            self.log("Make a pattern first.")
            return
        ch.append(pat)
        self.save_data()
        self.refresh_chain(select=len(ch) - 1)

    def chain_move(self, d):
        ch, i = self.chain(), self.chain_sel()
        if ch is None or i is None or not (0 <= i + d < len(ch)):
            return
        ch[i], ch[i + d] = ch[i + d], ch[i]
        self.save_data()
        self.refresh_chain(select=i + d)

    def chain_remove(self):
        ch, i = self.chain(), self.chain_sel()
        if ch is None or i is None:
            return
        del ch[i]
        self.save_data()
        self.refresh_chain(select=min(i, len(ch) - 1))

    # ----- stepping through a chain -----
    def chain_step(self, d):
        if self.pos is None:
            if d < 0:
                return
            if not self.chain():
                self.log("This chain is empty (or there is no chain). Add patterns to it first.")
                return
            self.run_chain = self.chain_var.get()
            self.go(0)
        else:
            if d < 0 and self.pos == 0:
                return
            self.go(self.pos + d)

    def jump_to_selected(self):
        i = self.chain_sel()
        if i is None:
            return
        self.run_chain = self.chain_var.get()
        self.go(i)

    def go(self, i):
        self.cancel_auto()
        steps = self.g()["chains"].get(self.run_chain) or []
        if i >= len(steps):
            self.finish_chain()
            return
        self.pos = i
        name = steps[i]
        self.apply_pattern(name, note="chain '%s' step %d/%d: %s" % (self.run_chain, i + 1, len(steps), name))
        nxt = ("next: " + steps[i + 1]) if i + 1 < len(steps) else "this is the last step"
        self.chain_status.config(text="Step %d/%d: %s\n%s" % (i + 1, len(steps), name, nxt), foreground="blue")
        self.refresh_chain()
        if self.auto.get():
            self.schedule_auto()

    def schedule_auto(self):
        try:
            secs = max(float(self.auto_secs.get()), 0.2)
        except ValueError:
            secs = 2.0
        self.auto_job = self.root.after(int(secs * 1000), lambda: self.go(self.pos + 1))

    def cancel_auto(self):
        if self.auto_job is not None:
            self.root.after_cancel(self.auto_job)
            self.auto_job = None

    def auto_changed(self):
        self.cancel_auto()
        if self.auto.get() and self.pos is not None:
            self.schedule_auto()

    def finish_chain(self):
        self.cancel_auto()
        self.pos = None
        self.chain_status.config(text="Chain finished. Press 'Send next' to start again.", foreground="gray")
        self.log("chain '%s' finished" % self.run_chain)
        self.refresh_chain()
        if self.end_off.get():
            self.all_off_quiet()
            self.send_state("chain ended: all off")

    def stop_chain(self, quiet=False):
        self.cancel_auto()
        if self.pos is not None:
            self.pos = None
            self.chain_status.config(text="Stopped. Press 'Send next' to start from the top.", foreground="gray")
            if not quiet:
                self.log("chain stopped (actuators left as they are)")
            self.refresh_chain()

    def key_step(self, d):
        # arrow keys step the chain, but not while typing in a box
        if isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry)):
            return
        self.chain_step(d)

    # ----- log -----
    def build_log(self):
        f = ttk.LabelFrame(self.root, text="Log", padding=4)
        f.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
        self.log_box = tk.Text(f, height=7, width=120)
        self.log_box.pack(fill="both", expand=True)

    def log(self, msg):
        self.log_box.insert("end", time.strftime("%H:%M:%S  ") + msg + "\n")
        if int(self.log_box.index("end").split(".")[0]) > 1000:
            self.log_box.delete("1.0", "200.0")
        self.log_box.see("end")

    def poll_log(self):
        while True:
            try:
                msg = self.log_q.get_nowait()
            except queue.Empty:
                break
            self.log(msg)
        self.root.after(100, self.poll_log)

    def on_close(self):
        self.cancel_auto()
        try:
            self.save_data()
        except Exception:
            pass
        if self.link.connected():
            self.all_off_quiet()
            self.send_state("closing: all off")
            self.link.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()