# 🚀 Quick Start - Running with TWS

## The Easiest Way

```bash
python run_tws.py
```

**That's it!** This automatically uses TWS (port 7497) instead of IB Gateway.

---

## What You Need

1. ✅ **Open TWS** (Trader Workstation)
2. ✅ **Log in**
3. ✅ **Enable API** (File → Global Configuration → API → Settings)
4. ✅ Run `python run_tws.py`

---

## Alternative Ways

### Interactive Launcher
```bash
python launcher.py
```
Then choose: `1` for TWS or `2` for IB Gateway

### Bash Script
```bash
./run_with_tws.sh
```

### Manual
```bash
export IB_USE_TWS=true
python app.py
```

---

## How to Know It's Working

You'll see:
```
Configured for TWS on port 7497
Connecting to TWS at 127.0.0.1:7497...
✓ Successfully connected to TWS
```

Instead of:
```
Configured for IB Gateway on port 4001
```

---

## Files Created for You

- **`run_tws.py`** ⭐ - Easiest way (use this!)
- **`launcher.py`** - Interactive chooser
- **`run_with_tws.sh`** - Bash script
- **`test_tws_connection.py`** - Test TWS is working

---

## Need Help?

See: `HOW_TO_RUN_WITH_TWS.md` for detailed instructions

