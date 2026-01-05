#!/bin/bash

echo "Starting Trading App with TWS..."

export IB_USE_TWS=true

echo "Configuration: IB_USE_TWS=$IB_USE_TWS"

if nc -z 127.0.0.1 7496 2>/dev/null; then
    echo "Port 7496 is open (TWS appears to be running)"
else
    echo "Port 7496 is not open - make sure TWS is running!"
    read -p "Press Enter to continue anyway, or Ctrl+C to exit..."
fi

echo "Starting app..."
python app.py
