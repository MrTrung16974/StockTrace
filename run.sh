#!/bin/bash

# Dừng các container hiện tại (nếu có)
docker compose down

# Xóa các image dangling (không bắt buộc nhưng giúp dọn dẹp)
# docker image prune -f

# Build lại các image không sử dụng cache
docker compose build --no-cache

# Khởi chạy các container ở chế độ background
docker compose up -d

echo "Đã chạy xong docker compose với tùy chọn xóa cache!"
