# 🔒 Безопасность паролей

Документация по безопасному хранению и управлению паролями в системе автотестирования UI.

---

## ✅ **Реализованные механизмы безопасности**

### 1. **Хеширование паролей**

Пароли **никогда** не хранятся в открытом виде. Используются современные алгоритмы хеширования.

#### **Приоритет алгоритмов:**

```python
# autotest_ui/settings.py
PASSWORD_HASHERS = [
    # 1. Argon2 - самый современный и безопасный
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    
    # 2. PBKDF2-SHA256 - стандарт Django
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    
    # 3. PBKDF2-SHA1 - для совместимости
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]
```

---

### 🏆 **Argon2 - Почему это лучшее?**

**Argon2** - победитель Password Hashing Competition (2015) и рекомендация OWASP 2024.

#### **Преимущества:**

- ✅ **Защита от GPU-атак**: использует много памяти
- ✅ **Защита от ASIC-атак**: сложный алгоритм
- ✅ **Защита от timing атак**: константное время сравнения
- ✅ **Настраиваемые параметры**: memory cost, time cost, parallelism

#### **Формат хранения:**

```
argon2$argon2id$v=19$m=102400,t=2,p=8$c29tZXNhbHQ$hash_here
└─────┘  └───────┘       └────────────────┘  └─────┘     └─────────┘
Алгоритм  Вариант    Параметры           Соль        Хеш
           (argon2id)  m=память, t=итерации,
                       p=параллелизм
```

---

### 🔑 **PBKDF2-SHA256 - Fallback**

Если Argon2 не установлен, используется **PBKDF2-SHA256** (стандарт Django).

#### **Характеристики:**

- ✅ **260,000 итераций** (OWASP рекомендует 100,000+)
- ✅ **SHA-256** хеш-функция
- ✅ **Случайная соль** для каждого пароля
- ✅ **Стандарт NIST SP 800-132**

#### **Формат хранения:**

```
pbkdf2_sha256$260000$randomsalt123$hashed_password_here
└─────────────┘  └──────┘ └───────────────┘  └──────────────────────┘
  Алгоритм   Итерации      Соль              Хеш
```

---

## 2. **Валидация паролей**

Система применяет 4 валидатора:

### ✅ **1. UserAttributeSimilarityValidator**
Пароль не должен быть схож с username, email, именем.

**Пример:**
- ❌ `username: john_doe` → `password: johndoe123` - **Отклонен**
- ✅ `username: john_doe` → `password: SecurePass123!` - **ОК**

### ✅ **2. MinimumLengthValidator**
Минимальная длина: **8 символов**

```python
{
    'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    'OPTIONS': {
        'min_length': 8,
    }
}
```

### ✅ **3. CommonPasswordValidator**
Пароль не должен быть в списке 20,000+ распространённых паролей.

**Пример:**
- ❌ `password`, `123456`, `qwerty` - **Отклонены**
- ✅ `MyS3cur3P@ss` - **ОК**

### ✅ **4. NumericPasswordValidator**
Пароль не должен состоять только из цифр.

**Пример:**
- ❌ `12345678` - **Отклонен**
- ✅ `Pass1234` - **ОК**

---

## 3. **Автоматическое улучшение хешей**

Django автоматически **перехеширует** пароли при входе:

```python
# Если в БД хранится:
pbkdf2_sha256$260000$...

# После входа пользователя автоматически обновится до:
argon2$argon2id$v=19$m=102400,t=2,p=8$...
```

Это обеспечивает **плавную миграцию** на более безопасные алгоритмы.

---

## 4. **Защита от атак**

### 🛡️ **Brute Force защита**

- ✅ **Медленное хеширование**: Argon2 и PBKDF2 специально замедлены
- ✅ **Высокая сложность**: 260,000+ итераций
- ✅ **Уникальные соли**: каждый пароль с уникальной солью

### 🛡️ **Rainbow Table защита**

- ✅ **Соль (случайный salt)**: невозможно создать предвычисленные таблицы
- ✅ **Уникальная соль для каждого пароля**

### 🛡️ **Timing Attack защита**

- ✅ **Константное время сравнения**: Django использует `constant_time_compare()`

---

## 🛠️ **Инструкция по установке**

### 1. Установите Argon2

```bash
pip install argon2-cffi
```

### 2. Проверьте настройки

```python
# autotest_ui/settings.py
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',  # ✅ Должно быть первым!
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    ...
]
```

### 3. Перезапустите сервер

```bash
cd autotest_ui
python manage.py runserver
```

### 4. Проверка работы

```bash
# Создайте нового пользователя
python manage.py createsuperuser

# Проверьте в БД
psql -U postgres -d autotest_ui -c "SELECT password FROM auth_user WHERE username='admin';"

# Должно начинаться с "argon2$..."
```

---

## 📊 **Сравнение алгоритмов**

| Алгоритм | Скорость подбора | GPU защита | ASIC защита | Рекомендация OWASP |
|------------|---------------------|--------------|----------------|----------------------|
| **Argon2** | 🐌 🐌 🐌 🐌 🐌         | ✅           | ✅             | ⭐ Лучшее             |
| **PBKDF2** | 🐌 🐌 🐌            | ⚠️           | ❌             | ✅ Хорошее            |
| **BCrypt** | 🐌 🐌 🐌            | ⚠️           | ⚠️             | ✅ Хорошее            |
| **SHA256** | 🚀 🚀 🚀 🚀 🚀      | ❌           | ❌             | ❌ Небезопасно      |
| **MD5**    | 🚀 🚀 🚀 🚀 🚀 🚀   | ❌           | ❌             | ❌ Критически!      |

**Легенда:**
- 🐌 = медленно (хорошо для безопасности)
- 🚀 = быстро (плохо для безопасности)

---

## 🔍 **Проверка в БД**

### Пример хешей в `auth_user` таблице:

```sql
SELECT id, username, password FROM auth_user;

-- Результат:
id | username | password
---+----------+-------------------------------------------------------------------------
1  | admin    | argon2$argon2id$v=19$m=102400,t=2,p=8$YWJjZGVm$hashedpasswordhere
2  | user1    | pbkdf2_sha256$260000$randomsalt$hashedpassword
```

✅ **Пароли никогда не хранятся в открытом виде!**

---

## 📚 **Дополнительные ресурсы**

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [Argon2 Specification](https://github.com/P-H-C/phc-winner-argon2)
- [Django Password Management](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/)
- [NIST SP 800-132](https://csrc.nist.gov/publications/detail/sp/800-132/final)

---

## ✅ **Соответствие стандартам**

- ✅ **OWASP Top 10 2021**: A02 - Cryptographic Failures
- ✅ **NIST SP 800-132**: PBKDF2 с 256-битным хешем
- ✅ **ISO 27001**: Безопасное хранение паролей
- ✅ **PCI DSS 4.0**: Requirement 8.3.2
- ✅ **GDPR**: Защита персональных данных

---

**🔒 Ваши пароли в безопасности с Argon2!**
