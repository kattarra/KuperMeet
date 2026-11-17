# KuperMeet — запуск на PythonAnywhere

Этот проект работает через Telegram long polling: веб-сервер и домен не нужны. Для постоянной работы на PythonAnywhere нужен платный тариф: Always-on tasks доступны платным аккаунтам, а исходящий интернет без allowlist-ограничений также предоставляется на платных тарифах.

## 1. Подготовить Telegram

1. Создай бота через @BotFather и сохрани токен в секрете.
2. Добавь бота администратором в канал модерации (MOD_CHANNEL).
3. Добавь бота администратором во все пять каналов, подписка на которые открывает 100 лайков.
4. Узнай свой Telegram numeric ID и укажи его в ADMIN_IDS.
5. Убедись, что бот может писать администраторам: каждый администратор должен хотя бы один раз открыть диалог с ботом и нажать Start.

## 2. Развернуть код

В Bash-консоли PythonAnywhere:

```bash
git clone https://github.com/kattarra/KuperMeet.git
cd KuperMeet
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Заполни .env реальными значениями. Для каналов используй @username публичного канала либо числовой Telegram chat ID. Не оставляй примерные значения из .env.example.

Минимальная конфигурация:

```env
BOT_TOKEN=секретный_токен
ADMIN_IDS=твой_numeric_telegram_id
ENABLE_TEEN_SEGMENT=false
TEEN_AGE_VERIFICATION_ENABLED=false
CHANNEL_KUPERCOIN=@реальный_username
CHANNEL_LUXDECOR=@реальный_username
CHANNEL_KUPERSHOP=@реальный_username
CHANNEL_4=@реальный_username
CHANNEL_5=@реальный_username
MOD_CHANNEL=@канал_модерации
REPORT_CHANNEL=@канал_жалоб
```

Не отправляй токен в GitHub, переписку или публичные сообщения. Файл .env уже исключён через .gitignore.

## 3. Первый запуск и проверка

Из каталога проекта:

```bash
source .venv/bin/activate
python -m compileall -q .
python -m unittest discover -s tests -v
python main.py
```

Проверь по порядку:
- /start и регистрацию взрослого профиля;
- получение анкеты модератором и approve;
- выдачу анкет, лайк и взаимный лайк;
- 10 лайков бесплатного аккаунта;
- проверку пяти подписок и увеличение лимита до 100;
- Premium invoice за 299 Telegram Stars и успешную активацию;
- отправку/принятие запроса на знакомство;
- жалобу, отклонение жалобы и блокировку.

Для платежей используй тестовый сценарий Telegram Stars, если он доступен для выбранного бота/окружения. Не проводи реальную оплату ради первичной проверки.

## 4. Постоянная работа

Для long polling нужен постоянно работающий процесс. В панели PythonAnywhere на платном тарифе создай Always-on task с командой:

```bash
cd /home/ТВОЙ_USERNAME/KuperMeet && /home/ТВОЙ_USERNAME/KuperMeet/.venv/bin/python /home/ТВОЙ_USERNAME/KuperMeet/main.py
```

Не запускай одновременно два экземпляра одного бота: они будут конфликтовать за получение Telegram updates.

## 5. Важные замечания

- Проверь, что тариф PythonAnywhere разрешает исходящие HTTPS-запросы к Telegram Bot API и предоставляет постоянно работающие задачи. Если нет — выбери тариф/хостинг, который это поддерживает.
- SQLite-файл kupermeet.db хранится рядом с приложением. Настрой регулярные резервные копии.
- Не включай подростковый сегмент: он закрыт до отдельной реальной проверки возраста и дополнительных защитных механизмов.
- Перед публичным запуском проверь тексты правил сервиса, политику конфиденциальности, возрастные ограничения и процесс обработки жалоб.
