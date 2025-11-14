from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from .models import Event
import json
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import parse as defused_parse
import os
import uuid
from datetime import datetime

# Папка для хранения файлов
UPLOAD_FOLDER = os.path.join(settings.MEDIA_ROOT, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def index(request):
    json_files = []
    xml_files = []
    all_events = []

    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if filename.endswith('.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and all(k in item for k in ['title', 'description', 'date', 'location', 'organizer']):
                                all_events.append(item)
                    json_files.append({
                        'name': filename,
                        'data': data
                    })
            except:
                pass
        elif filename.endswith('.xml'):
            try:
                tree = defused_parse(filepath)
                root = tree.getroot()
                if root.tag == 'events':
                    for event_elem in root.findall('event'):
                        event_data = {}
                        for child in event_elem:
                            event_data[child.tag] = child.text
                        if all(k in event_data for k in ['title', 'description', 'date', 'location', 'organizer']):
                            all_events.append(event_data)
                    xml_files.append({
                        'name': filename,
                        'data': [event_data for event_elem in root.findall('event') for event_data in [{}]]
                    })
            except:
                pass

    context = {
        'all_events': all_events,
    }
    return render(request, 'events/index.html', context)

def add_event(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        date = request.POST.get('date')
        location = request.POST.get('location')
        organizer = request.POST.get('organizer')
        format_type = request.POST.get('format', 'json')
        save_to_db = request.POST.get('save_to_db')  # checkbox

        # Валидация данных
        errors = []
        if not title or len(title) > 200:
            errors.append("Название должно быть заполнено и ≤ 200 символов.")
        if not date:
            errors.append("Дата обязательна.")
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d')
            if parsed_date.year < 1900 or parsed_date.year > 2100:
                errors.append("Дата должна быть в пределах 1900–2100 года.")
            if parsed_date.strftime('%Y-%m-%d') != date:
                errors.append("Дата указана в неправильном формате или не существует.")
        except ValueError:
            errors.append("Дата должна быть в формате ГГГГ-ММ-ДД.")

        if not location or len(location) > 300:
            errors.append("Место не может быть пустым и превышать 300 символов.")
        if not organizer or len(organizer) > 200:
            errors.append("Организатор не может быть пустым и превышать 200 символов.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'events/add_event.html')

        # Подготовка данных
        data = {
            "title": title,
            "description": description,
            "date": date,
            "location": location,
            "organizer": organizer
        }

        # Сохранение в БД
        if save_to_db:
            # Проверка дубликатов в БД
            existing = Event.objects.filter(
                title=title,
                date=date,
                location=location,
                organizer=organizer
            ).first()

            if existing:
                messages.warning(request, f"Мероприятие '{title}' уже существует в базе данных.")
            else:
                Event.objects.create(**data)
                messages.success(request, f"Мероприятие '{title}' сохранено в базу данных.")

        # Сохранение в файл
        if format_type in ['json', 'xml']:
            safe_name = f"event_{uuid.uuid4().hex[:8]}.{format_type}"
            filepath = os.path.join(UPLOAD_FOLDER, safe_name)

            if format_type == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump([data], f, ensure_ascii=False, indent=2)
            elif format_type == 'xml':
                root = ET.Element("events")
                event_elem = ET.SubElement(root, "event")
                for key, value in data.items():
                    child = ET.SubElement(event_elem, key)
                    child.text = str(value)
                tree = ET.ElementTree(root)
                tree.write(filepath, encoding='utf-8', xml_declaration=True)

            messages.success(request, f"Мероприятие '{title}' сохранено в файл {safe_name}")

        return redirect('events:add_event')

    return render(request, 'events/add_event.html')

def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        original_name = uploaded_file.name

        # Проверка расширения
        if not (original_name.lower().endswith('.json') or original_name.lower().endswith('.xml')):
            messages.error(request, "Файл должен быть .json или .xml")
            return redirect('events:upload_file')

        # Генерация безопасного имени
        ext = os.path.splitext(original_name)[1]
        safe_name = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, safe_name)

        # Сохраняем файл
        with open(filepath, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # Проверка валидности
        is_valid = False
        events_data = []

        try:
            if ext == '.json':
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and all(k in item for k in ['title', 'description', 'date', 'location', 'organizer']):
                                # Валидация каждого элемента
                                title = item.get('title')
                                date = item.get('date')
                                if not title or len(title) > 200:
                                    messages.error(request, f"Название '{title}' в файле слишком длинное.")
                                    os.remove(filepath)
                                    return redirect('events:upload_file')
                                try:
                                    parsed_date = datetime.strptime(date, '%Y-%m-%d')
                                    if parsed_date.year < 1900 or parsed_date.year > 2100:
                                        messages.error(request, f"Дата '{date}' вне диапазона.")
                                        os.remove(filepath)
                                        return redirect('events:upload_file')
                                    if parsed_date.strftime('%Y-%m-%d') != date:
                                        messages.error(request, f"Дата '{date}' не существует.")
                                        os.remove(filepath)
                                        return redirect('events:upload_file')
                                except ValueError:
                                    messages.error(request, f"Дата '{date}' указана в неправильном формате.")
                                    os.remove(filepath)
                                    return redirect('events:upload_file')
                                events_data.append(item)
                        is_valid = len(events_data) > 0
            elif ext == '.xml':
                tree = defused_parse(filepath)
                root = tree.getroot()
                if root.tag == 'events':
                    for event_elem in root.findall('event'):
                        event_data = {}
                        for child in event_elem:
                            event_data[child.tag] = child.text
                        if all(k in event_data for k in ['title', 'description', 'date', 'location', 'organizer']):
                            # Валидация каждого элемента
                            title = event_data.get('title')
                            date = event_data.get('date')
                            if not title or len(title) > 200:
                                messages.error(request, f"Название '{title}' в файле слишком длинное.")
                                os.remove(filepath)
                                return redirect('events:upload_file')
                            try:
                                parsed_date = datetime.strptime(date, '%Y-%m-%d')
                                if parsed_date.year < 1900 or parsed_date.year > 2100:
                                    messages.error(request, f"Дата '{date}' вне диапазона.")
                                    os.remove(filepath)
                                    return redirect('events:upload_file')
                                if parsed_date.strftime('%Y-%m-%d') != date:
                                    messages.error(request, f"Дата '{date}' не существует.")
                                    os.remove(filepath)
                                    return redirect('events:upload_file')
                            except ValueError:
                                messages.error(request, f"Дата '{date}' указана в неправильном формате.")
                                os.remove(filepath)
                                return redirect('events:upload_file')
                            events_data.append(event_data)
                    is_valid = len(events_data) > 0
        except Exception as e:
            messages.error(request, f"Ошибка чтения файла: {str(e)}")
            os.remove(filepath)
            return redirect('events:upload_file')

        if is_valid:
            # Проверка дубликатов в БД
            duplicates_found = False
            for new_event in events_data:
                existing = Event.objects.filter(
                    title=new_event.get('title'),
                    date=new_event.get('date'),
                    location=new_event.get('location'),
                    organizer=new_event.get('organizer')
                ).first()
                if existing:
                    messages.error(request, f"Мероприятие '{new_event['title']}' уже существует в базе данных.")
                    duplicates_found = True

            if duplicates_found:
                os.remove(filepath)
                return redirect('events:upload_file')

            messages.success(request, f"Файл '{original_name}' успешно загружен и обработан. Добавлено {len(events_data)} мероприятий.")
        else:
            os.remove(filepath)
            messages.error(request, f"Файл '{original_name}' не прошёл проверку валидности и был удалён.")

        return redirect('events:upload_file')

    return render(request, 'events/upload_file.html')

def view_files(request):
    json_files = []
    xml_files = []

    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if filename.endswith('.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    json_files.append({
                        'name': filename,
                        'data': data
                    })
            except:
                pass
        elif filename.endswith('.xml'):
            try:
                tree = defused_parse(filepath)
                root = tree.getroot()
                events_list = []
                for event_elem in root.findall('event'):
                    event_data = {}
                    for child in event_elem:
                        event_data[child.tag] = child.text
                    events_list.append(event_data)
                xml_files.append({
                    'name': filename,
                    'data': events_list
                })
            except:
                pass

    context = {
        'json_files': json_files,
        'xml_files': xml_files,
    }
    return render(request, 'events/view_files.html', context)

def view_db(request):
    events = Event.objects.all()
    return render(request, 'events/view_db.html', {'events': events})

def search_events(request):
    query = request.GET.get('q', '')
    events = Event.objects.filter(
        title__icontains=query
    ) | Event.objects.filter(
        location__icontains=query
    ) | Event.objects.filter(
        organizer__icontains=query
    )
    data = [
        {
            'id': e.id,
            'title': e.title,
            'date': e.date.isoformat(),
            'location': e.location,
            'organizer': e.organizer,
        }
        for e in events
    ]
    return JsonResponse(data, safe=False)

def get_event(request, event_id):
    event = Event.objects.get(id=event_id)
    data = {
        'id': event.id,
        'title': event.title,
        'date': event.date.isoformat(),
        'location': event.location,
        'organizer': event.organizer,
        'description': event.description,
    }
    return JsonResponse(data)

def update_event(request, event_id):
    if request.method == 'POST':
        event = Event.objects.get(id=event_id)
        event.title = request.POST.get('title')
        event.date = request.POST.get('date')
        event.location = request.POST.get('location')
        event.organizer = request.POST.get('organizer')
        event.description = request.POST.get('description')

        # Валидация
        errors = []
        if not event.title or len(event.title) > 200:
            errors.append("Название должно быть ≤ 200 символов.")
        try:
            parsed_date = datetime.strptime(event.date, '%Y-%m-%d')
            if parsed_date.year < 1900 or parsed_date.year > 2100:
                errors.append("Дата вне диапазона.")
            if parsed_date.strftime('%Y-%m-%d') != event.date:
                errors.append("Дата указана в неправильном формате или не существует.")
        except ValueError:
            errors.append("Дата должна быть в формате ГГГГ-ММ-ДД.")

        if not event.location or len(event.location) > 300:
            errors.append("Место должно быть ≤ 300 символов.")
        if not event.organizer or len(event.organizer) > 200:
            errors.append("Организатор должен быть ≤ 200 символов.")

        if errors:
            return JsonResponse({'success': False, 'errors': errors})

        event.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

def delete_event(request, event_id):
    if request.method == 'POST':
        event = Event.objects.get(id=event_id)
        event.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'})