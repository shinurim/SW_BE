from django.urls import path
from .views_save import (save_segment,retrieve_segment,list_segments,login_user,
                         delete_segment,signup,mypage_detail, 
                         mypage_update_profile, mypage_change_password,)

urlpatterns = [
    path("save/save_segment", save_segment), 
    path("auth/login", login_user),   
    path("segments", list_segments), 
    path("insights/<int:segment_id>", retrieve_segment), 
    path("segments/delete", delete_segment, name="segment_delete"),   
    path("auth/signup", signup, name="signup"),  
    path("mypage", mypage_detail, name="mypage_detail"),   
    path("user/profile", mypage_update_profile, name="mypage_update_profile"), 
    path("mypage/password", mypage_change_password, name="mypage_change_password"),   
]