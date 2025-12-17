from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import UserData
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view 
import json
from .models import SegmentHistory
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import UserData
from typing import Optional, Any, List

def _keywords_to_list(s: Optional[str]) -> List[str]:
    if not s:
        return []
    return [k.strip() for k in s.split(",") if k.strip()]


def _keywords_from_any(value: Any) -> str:
    if isinstance(value, list):
        return ",".join([str(k).strip() for k in value if str(k).strip()])
    if isinstance(value, str):
        return value.strip()
    return ""



#로그인
@api_view(['POST'])
@csrf_exempt
def login_user(request):
    user_id = request.data.get('user_id')
    password = request.data.get('password')

    try:
        person = UserData.objects.get(user_id=user_id)

        if person.password == password:
            return JsonResponse({
                "message": "로그인 성공",
            }, status=200)

        else:
            return JsonResponse({"error": "비밀번호가 일치하지 않습니다."})

    except UserData.DoesNotExist:
        return JsonResponse({"error": "존재하지 않는 사용자입니다."})
    
#회원가입
@csrf_exempt
@require_http_methods(["POST"])
def signup(request):
    try:
        data = json.loads(request.body.decode("utf-8"))

        user_id  = data.get("user_id")
        password = data.get("password")
        email    = data.get("email")
        keywords = data.get("keywords", "")  

        user = UserData.objects.create(
            user_id=user_id,
            password=password,
            email=email,
            keywords=keywords,
        )

        return JsonResponse(
            {"message": "회원가입 성공", "user_id": user.id},
            status=201,
        )

    except Exception as e:
        print("signup error:", e)
        return JsonResponse(
            {"message": "회원가입 실패", "error": str(e)},
            status=400,
        )
    
#마이페이지
@api_view(["GET"])
def mypage_detail(request):
    user_id = request.query_params.get("user_id")
    if not user_id:
        return Response({"error": "user_id가 필요합니다."},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        user = UserData.objects.get(user_id=user_id)
    except UserData.DoesNotExist:
        return Response({"error": "해당 사용자를 찾을 수 없습니다."},
                        status=status.HTTP_404_NOT_FOUND)

    data = {
        "user_id": user.user_id,
        "email": user.email or "",
        "keywords": _keywords_to_list(user.keywords),
    }
    return Response(data, status=status.HTTP_200_OK)


# 프로필 변경
@api_view(["PATCH"])
def mypage_update_profile(request):
    user_id = request.data.get("user_id")
    if not user_id:
        return Response({"error": "user_id가 필요합니다."},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        user = UserData.objects.get(user_id=user_id)
    except UserData.DoesNotExist:
        return Response({"error": "해당 사용자를 찾을 수 없습니다."},
                        status=status.HTTP_404_NOT_FOUND)

    email = request.data.get("email")
    if email is not None:
        user.email = email

    keywords_value = request.data.get("keywords")
    if keywords_value is not None:
        user.keywords = _keywords_from_any(keywords_value)

    user.save()

    resp_user = {
        "user_id": user.user_id,
        "email": user.email or "",
        "keywords": user.keywords or "",
    }

    return Response(
        {"message": "프로필이 저장되었습니다.", "user": resp_user},
        status=status.HTTP_200_OK,
    )


# 비밀번호 변경
@api_view(["PATCH"])
def mypage_change_password(request):
    user_id = request.data.get("user_id")
    current = request.data.get("currentPassword")
    new = request.data.get("newPassword")

    if not user_id or not current or not new:
        return Response(
            {"message": "user_id, currentPassword, newPassword가 필요합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = UserData.objects.get(user_id=user_id)
    except UserData.DoesNotExist:
        return Response(
            {"message": "해당 사용자를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if user.password != current:
        return Response(
            {"message": "현재 비밀번호가 올바르지 않습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.password = new
    user.save()

    return Response(
        {"message": "비밀번호가 성공적으로 변경되었습니다."},
        status=status.HTTP_200_OK,
    )


#세그먼트 저장
@csrf_exempt
@require_http_methods(["POST"])
def save_segment(request):
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "JSON 파싱 실패"}, status=400)

    user_id      = (body.get("user_id") or "").strip()
    segment_name = (body.get("segment_name") or "").strip()
    user_input   = (body.get("user_input") or "").strip()
    stage3       = body.get("stage3")
    insight      = body.get("insight")

    if not user_id:
        return JsonResponse({"error": "user_id가 필요합니다."}, status=400)

    if not segment_name:
        return JsonResponse({"error": "segment_name은 필수입니다."}, status=400)

    if not isinstance(stage3, dict):
        return JsonResponse({"error": "stage3는 dict여야 합니다."}, status=400)

    if not isinstance(insight, dict):
        return JsonResponse({"error": "insight는 dict여야 합니다."}, status=400)

    seg = SegmentHistory.objects.create(
        user_id=user_id,                
        segment_name=segment_name,
        user_input=user_input,
        main=stage3.get("main"),
        sub=stage3.get("sub"),
        stage3=stage3,
        insight=insight,
    )

    return JsonResponse(
        {"message": "세그먼트 저장 완료", "id": seg.id},
        status=201,
        json_dumps_params={"ensure_ascii": False},
    )

#세그먼트 삭제
@csrf_exempt
@require_http_methods(["POST"])
def delete_segment(request):
    """
    POST /api/v1/segments/delete
    body: { "id": <segment_id>, "user_id": <로그인 유저 id> }
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    seg_id = payload.get("id")
    user_id = payload.get("user_id")

    if not seg_id or not user_id:
        return JsonResponse(
            {"error": "id와 user_id가 필요합니다."},
            status=400,
        )

    try:
        segment = SegmentHistory.objects.get(id=seg_id, user_id=user_id)
    except SegmentHistory.DoesNotExist:
        return JsonResponse(
            {"error": "해당 세그먼트를 찾을 수 없습니다."},
            status=404,
        )

    segment.delete()

    return JsonResponse(
        {
            "message": "세그먼트가 삭제되었습니다.",
            "id": seg_id,
        }
    )

#저장된 세그먼트 리스트
@require_http_methods(["GET"])
def list_segments(request):
    user_id = request.GET.get("user_id")

    if not user_id:
        return JsonResponse({"error": "user_id가 필요합니다."}, status=400)

    qs = SegmentHistory.objects.filter(user_id=user_id).order_by("-created_at")

    items = []
    for seg in qs:
        stage3 = seg.stage3 or {}
        items.append({
            "id": seg.id,
            "segment_name": seg.segment_name,
            "count": stage3.get("count"),
            "main": stage3.get("main") or seg.main,
            "sub": stage3.get("sub") or seg.sub,
        })

    return JsonResponse({"segments": items},
                        json_dumps_params={"ensure_ascii": False})

#저장된 세그먼트 인사이트
@require_http_methods(["GET"])
def retrieve_segment(request, segment_id):
    user_id = request.GET.get("user_id")
    if not user_id:
        return JsonResponse({"error": "user_id가 필요합니다."}, status=400)

    try:
        seg = SegmentHistory.objects.get(id=segment_id, user_id=user_id)
    except SegmentHistory.DoesNotExist:
        return JsonResponse({"error": "Segment not found"}, status=404)

    stage3 = seg.stage3 or {}

    return JsonResponse({
        "id": seg.id,
        "segment_name": seg.segment_name,
        "user_input": seg.user_input,
        "main": stage3.get("main") or seg.main,
        "sub": stage3.get("sub") or seg.sub,
        "stage3": stage3,
        "insight": seg.insight,
    }, json_dumps_params={"ensure_ascii": False})
