from django.core.exceptions import ValidationError
import imghdr


def validate_image_file(file):
    """
    Валидация загружаемого файла - только изображения.
    Проверяет расширение, MIME-тип и фактическое содержимое файла.
    
    Args:
        file: Загружаемый файл (InMemoryUploadedFile или TemporaryUploadedFile)
    
    Raises:
        ValidationError: Если файл не является корректным изображением
    
    Returns:
        file: Валидный файл изображения
    """
    # Разрешённые расширения
    valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif']
    
    # Проверка расширения файла
    if hasattr(file, 'name'):
        ext = file.name.split('.')[-1].lower() if '.' in file.name else ''
        if not ext or ext not in valid_extensions:
            raise ValidationError(
                f'Неподдерживаемый формат файла "{ext}". '
                f'Разрешены только изображения: {", ".join(valid_extensions.upper())}'
            )
    
    # Проверка MIME-типа
    if hasattr(file, 'content_type'):
        valid_mime_types = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/bmp', 'image/webp', 'image/tiff'
        ]
        if file.content_type not in valid_mime_types:
            raise ValidationError(
                f'Недопустимый тип файла "{file.content_type}". '
                f'Файл не является изображением.'
            )
    
    # Дополнительная проверка содержимого файла
    try:
        # Сохраняем текущую позицию
        current_position = file.tell() if hasattr(file, 'tell') else 0
        
        # Перемещаемся в начало
        if hasattr(file, 'seek'):
            file.seek(0)
        
        # Проверяем фактический формат изображения
        image_type = imghdr.what(file)
        
        # Возвращаем указатель обратно
        if hasattr(file, 'seek'):
            file.seek(current_position)
        
        if image_type not in ['jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'rgb']:
            raise ValidationError(
                'Файл не является корректным изображением. '
                'Содержимое файла не соответствует формату изображения.'
            )
    except (AttributeError, OSError) as e:
        raise ValidationError(
            f'Не удалось прочитать файл как изображение: {str(e)}'
        )
    finally:
        # Убеждаемся, что указатель в начале для дальнейшей обработки
        if hasattr(file, 'seek'):
            try:
                file.seek(0)
            except:
                pass
    
    # Проверка размера файла (максимум 10 MB)
    max_size = 10 * 1024 * 1024  # 10 MB
    if hasattr(file, 'size') and file.size > max_size:
        raise ValidationError(
            f'Размер файла ({file.size / (1024*1024):.2f} MB) '
            f'превышает максимально допустимый ({max_size / (1024*1024):.0f} MB)'
        )
    
    return file
