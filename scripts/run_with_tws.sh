#!/bin/bash

cd "${HOME}/App/trading" || exit 1
echo "Starting Trading App with TWS..."

export IB_USE_TWS=false
export APP_PATH="${HOME}/App/trading"

echo "Configuration: IB_USE_TWS=$IB_USE_TWS"

if nc -z 127.0.0.1 7496 2>/dev/null; then
    echo "Port 7496 is open (TWS appears to be running)"
else
    echo "Port 7496 is not open - make sure TWS is running!"
fi

echo "Starting app..."
python "${APP_PATH}/app.py"
