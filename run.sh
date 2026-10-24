#!/bin/bash
set -e

# Chỉ build API và tận dụng cache dependency/Docker layer.
docker compose build api

# Chỉ thay container có thay đổi; không dừng PostgreSQL/Redis vô ích.
docker compose up -d --remove-orphans

echo "StockTrace đã được build và khởi chạy."
