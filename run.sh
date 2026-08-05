#!/bin/bash

# Cập nhật file requirements.txt từ uv / pyproject.toml để đảm bảo Docker luôn nhận dependency mới nhất
if command -v uv &> /dev/null; then
    echo "Đang đồng bộ và cập nhật file requirements.txt từ uv..."
    uv export --no-hashes --no-dev --no-emit-project -o requirements.txt
else
    echo "Lưu ý: Không tìm thấy lệnh 'uv', tiếp tục sử dụng file requirements.txt hiện tại..."
fi

# Dừng các container hiện tại (nếu có)
docker compose down

# Xóa các image dangling (không bắt buộc nhưng giúp dọn dẹp)
# docker image prune -f

# Build lại các image không sử dụng cache
docker compose build --no-cache

# Khởi chạy các container ở chế độ background
docker compose up -d

echo "Đã chạy xong docker compose với tùy chọn xóa cache!"
