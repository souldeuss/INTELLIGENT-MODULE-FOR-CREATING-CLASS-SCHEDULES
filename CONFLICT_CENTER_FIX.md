# 🔧 Виправлення Conflict Center

## Проблеми які були виправлені

### 1. ❌ Конфлікти не оновлювались

**Причина:** Компонент використовував mock дані замість реального API  
**Рішення:**

- Видалено всі mock дані
- Використовується тільки реальний API endpoint `/api/schedule/conflicts`
- Додано обробку помилок з відображенням в snackbar

### 2. ❌ Неможливо видалити неактуальні конфлікти

**Причина:** Не було функції видалення класів  
**Рішення:**

- Додано функцію `handleDeleteClass()`
- Додано кнопку видалення (іконка Delete) для кожного конфлікту
- Підтвердження видалення через діалог
- Оновлення списку після видалення

## Зміни в коді

### Frontend: ConflictCenter.tsx

1. **Імпорти:**

```typescript
import { DeleteIcon } from "@mui/icons-material";
import { deleteScheduledClass } from "../services/api";
```

2. **Стан:**

```typescript
const [deletingId, setDeletingId] = useState<number | null>(null);
```

3. **Функція видалення:**

```typescript
const handleDeleteClass = async (classId: number) => {
  if (!window.confirm("Ви впевнені?")) return;

  setDeletingId(classId);
  try {
    await deleteScheduledClass(classId);
    setSnackbar({
      open: true,
      message: "Заняття видалено",
      severity: "success",
    });
    loadConflicts();
    onConflictResolved?.();
  } catch (error: any) {
    setSnackbar({
      open: true,
      message: "Помилка видалення",
      severity: "error",
    });
  } finally {
    setDeletingId(null);
  }
};
```

4. **UI - Кнопка видалення:**

```typescript
<Tooltip title="Видалити заняття">
  <IconButton
    size="small"
    color="error"
    onClick={() => handleDeleteClass(conflict.details.class_id!)}
    disabled={deletingId === conflict.details.class_id}
  >
    <DeleteIcon fontSize="small" />
  </IconButton>
</Tooltip>
```

5. **Завантаження конфліктів:**

```typescript
const loadConflicts = useCallback(async () => {
  setLoading(true);
  try {
    const response = await checkConflicts();
    setConflicts(response.data || []);
  } catch (error: any) {
    console.error("Failed to load conflicts:", error);
    setSnackbar({
      open: true,
      message: "Помилка завантаження конфліктів",
      severity: "error",
    });
    setConflicts([]);
  } finally {
    setLoading(false);
    setLastUpdated(new Date());
  }
}, []);
```

### Backend: schedule.py

Endpoint вже існував:

```python
@router.delete("/class/{class_id}", status_code=200)
def delete_scheduled_class(class_id: int, db: Session = Depends(get_db)):
    """Видалити заняття з розкладу."""
    scheduled_class = db.query(ScheduledClass).filter(ScheduledClass.id == class_id).first()
    if not scheduled_class:
        raise HTTPException(status_code=404, detail="Заняття не знайдено")

    if scheduled_class.is_locked:
        raise HTTPException(status_code=400, detail="Неможливо видалити заблоковане заняття")

    db.delete(scheduled_class)
    db.commit()

    return {"success": True, "message": "Заняття видалено"}
```

## Як використовувати

### 1. Перегляд конфліктів

1. Відкрийте меню **"Конфлікти"** в лівому сайдбарі
2. Побачите список усіх конфліктів:
   - 🔴 **Жорсткі** (червоні) - критичні конфлікти (викладач/аудиторія/група зайняті)
   - 🟠 **М'які** (помаранчеві) - рекомендації (місткість, переваги)

### 2. Оновлення списку

- Натисніть іконку 🔄 **Refresh** у правому верхньому куті
- Або почекайте автоматичного оновлення (кожні 5 секунд)

### 3. Перегляд деталей

- Натисніть на стрілку **▼** щоб розгорнути деталі конфлікту
- Побачите:
  - Зачеплені елементи (курси, групи)
  - AI рекомендації для вирішення

### 4. Видалення неактуального заняття

1. Знайдіть конфлікт який треба видалити
2. Натисніть червону іконку **🗑️ Delete**
3. Підтвердіть видалення в діалозі
4. Заняття буде видалено, список конфліктів оновиться

**⚠️ Примітка:** Не можна видалити заблоковані (is_locked=true) заняття.

### 5. Перехід до заняття

- Натисніть іконку **👁️ View** щоб перейти до редагування заняття

## Приклади конфліктів

### Жорсткий конфлікт викладача

```
🔴 Конфлікт викладача: доц. Петренко має 2 заняття одночасно
Понеділок, 10:00-11:30
- Математичний аналіз (КІ-21)
- Програмування (КН-22)

💡 Рекомендації:
- Перемістити одне з занять на інший час
- Призначити іншого викладача
```

**Дія:** Видаліть одне з занять або перемістіть

### Жорсткий конфлікт аудиторії

```
🔴 Конфлікт аудиторії: ауд. 301 зайнята двічі
Середа, 14:00-15:30
- Фізика (ФІ-21)
- Хімія (ХМ-22)

💡 Рекомендації:
- Перемістити одне з занять в іншу аудиторію
- Змінити час одного з занять
```

**Дія:** Видаліть або змініть аудиторію

### М'який конфлікт місткості

```
🟠 Місткість: група КН-21 (35 осіб) у ауд. 201 (30 місць)
П'ятниця, 12:00-13:30

💡 Рекомендації:
- Перемістити в аудиторію більшої місткості
```

**Дія:** Можна залишити або перемістити в більшу аудиторію

## Технічні деталі

### API Endpoints

- `GET /api/schedule/conflicts` - отримати список конфліктів
- `DELETE /api/schedule/class/{class_id}` - видалити заняття

### Структура відповіді conflicts

```json
[
  {
    "id": "1",
    "type": "hard" | "soft",
    "category": "teacher" | "room" | "group" | "capacity",
    "message": "Опис конфлікту",
    "details": {
      "class_id": 15,
      "timeslot": "Понеділок, 10:00-11:30",
      "affected_items": ["Курс 1", "Курс 2"]
    },
    "suggestions": ["Рекомендація 1", "Рекомендація 2"]
  }
]
```

### Автооновлення

- **За замовчуванням:** Кожні 5 секунд
- **Налаштування:** `refreshInterval` prop (мс)
- **Вимкнення:** `autoRefresh={false}` prop

```typescript
<ConflictCenter
  autoRefresh={true}
  refreshInterval={5000}
  onConflictResolved={() => console.log("Resolved!")}
/>
```

## Відладка

### Конфлікти не завантажуються

1. Перевірте чи запущений backend:

```bash
cd backend
python -m uvicorn app.main:app --reload
```

2. Перевірте консоль браузера (F12) на помилки

3. Перевірте endpoint вручну:

```bash
curl http://localhost:8000/api/schedule/conflicts
```

### Не вдається видалити конфлікт

**Помилка:** "Неможливо видалити заблоковане заняття"  
**Причина:** Заняття має `is_locked=true`  
**Рішення:** Спочатку розблокуйте заняття в редакторі розкладу

## Подальші покращення

### Планується додати:

1. **Масове видалення**

   - Чекбокси для вибору кількох конфліктів
   - Кнопка "Видалити обрані"

2. **Автоматичне вирішення**

   - Кнопка "Виправити автоматично" для AI рішення
   - Застосування рекомендацій одним кліком

3. **Фільтрація**

   - Фільтр за типом (жорсткі/м'які)
   - Фільтр за категорією (викладач/аудиторія/група)

4. **Історія**

   - Логування вирішених конфліктів
   - Статистика покращень

5. **Експорт**
   - Експорт списку конфліктів у PDF/Excel
   - Звіт про якість розкладу

---

**Версія:** 2.1.0  
**Дата оновлення:** 02.01.2026  
**Автор:** DRL Scheduler Team
