# tsweb_py

CLI клиент для системы тестирования TestSys (tsweb.ru/t/)

## Установка

```bash
cd tsweb_cli_new
pip install -e .
```

## Использование

### Первый запуск

1. **Авторизация:**
```bash
tsweb_py login
```

2. **Выбор контеста:**
```bash
tsweb_py local set-contest
```

3. **Получение списка задач и компиляторов:**
```bash
tsweb_py local parse
```

### Основные команды

**Просмотр конфигурации:**
```bash
tsweb_py local show
```

**Просмотр информации о пользователе:**
```bash
tsweb_py info
```

**Отправка решения:**
```bash
tsweb_py submit solution.cpp -p 12A -l 1
```
где `-p` - задача, а `-l` - компилятор (по порядку, удобнее ставить по дефолту `tsweb_py local set-compiler`)
Или автоматически определить задачу по имени файла:
```bash
tsweb_py submit 12A.cpp
```

**Просмотр посылок:**
```bash
tsweb_py submissions
```

**Установка компилятора по умолчанию:**
```bash
tsweb_py local set-compiler
```

### Структура

- `~/.tsweb_py.global` - глобальная конфигурация (credentials)
- `~/.tsweb_py.cookies` - cookies сессии (включая contest_id) - сохраняются через pickle
- `.tsweb_py.local` - локальная конфигурация (problems, compilers, default_lang)

## Возможности

- Автоматическая авторизация и сохранение сессии
- Переключение между контестами
- Отправка решений с отслеживанием результатов
- Просмотр всех посылок
- Детальная информация о тестах
- Цветной вывод результатов (OK, WA, TL и т.д.)

## Требования

- Python 3.8+
- requests
- click
- beautifulsoup4
- rich
