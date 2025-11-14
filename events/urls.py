from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.add_event, name='add_event'),
    path('upload/', views.upload_file, name='upload_file'),
    path('view_files/', views.view_files, name='view_files'),
    path('view_db/', views.view_db, name='view_db'),
    path('api/search/', views.search_events, name='search_events'),
    path('api/event/<int:event_id>/', views.get_event, name='get_event'),
    path('api/update/<int:event_id>/', views.update_event, name='update_event'),
    path('api/delete/<int:event_id>/', views.delete_event, name='delete_event'),
]