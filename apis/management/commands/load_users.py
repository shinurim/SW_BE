# apis/management/commands/load_users.py

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from apis.models import UserData  # 경로 맞게!

class Command(BaseCommand):
    help = "user.csv 내용을 UserData(users 테이블)에 적재합니다."

    def handle(self, *args, **options):
        # manage.py가 있는 BASE_DIR / 'user.csv'
        csv_path = Path(settings.BASE_DIR) / "user.csv"

        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f"CSV 파일이 없습니다: {csv_path}"))
            return

        created = 0
        with csv_path.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # ⚠ 여기 키 이름은 CSV 헤더와 반드시 같아야 함
                user_id = row["user_id"]
                password = row["password"]
                name = row.get("name") or ""
                email = row.get("email") or ""
                phone_number = row.get("phone_number") or ""

                # 이미 있는 user_id는 스킵하고 싶다면 get_or_create 사용
                obj, is_created = UserData.objects.get_or_create(
                    user_id=user_id,
                    defaults={
                        "password": password,
                        "name": name,
                        "email": email,
                        "phone_number": phone_number,
                    },
                )
                if is_created:
                    created += 1

        self.stdout.write(self.style.SUCCESS(f"{created}개 user 생성 완료"))
