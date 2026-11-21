## [0.4.1] — 21.11.2026

### 🐛 Исправления

- Fix(MEMORY): MEMTOOLS: надёжная запись фактов — очередь
  - дедуп и разбор JSON-строк
  - parseLoose: терпимый парсинг фактов при мусоре после JSON
  - описания think/facts: просить массив атомных фактов, не JSON-строку
  - saveChain: последовательная запись вместо параллельной (потери/id)
  - savedFacts: идемпотентность по категории, тексту, тегам ([4b99edb](https://github.com/intervisionlord/ANIMA/commit/4b99edb10820c9c078726d670b9ed1803c5585cd))

### 📚 Документация

- *(RCC)* Обновлена структура проекта ([ca4b585](https://github.com/intervisionlord/ANIMA/commit/ca4b585f868870cf7e6fe01ed348ea805ecfc201))
- *(RCC)* Обновлена документация ([fb23788](https://github.com/intervisionlord/ANIMA/commit/fb23788f9f061384dad5c02593c860daa9a5b29c))
  - Обновлен README
  - Добавлена PDF версия

### 🧹 Рефакторинг

- *(MEMORY)* MEMTOOLS: Рефакторинг ([4d6bf0f](https://github.com/intervisionlord/ANIMA/commit/4d6bf0fbba4582c883e94317db92787725978604))
  - Убраны факты у мышления
  - уточнено описание мышление и текст для модели
- *(VOICE)* Откллючение инструментов в дочерней сессии ([a665179](https://github.com/intervisionlord/ANIMA/commit/a6651790bd3fcdb48fcba860b2057d4930842b18))
- *(MEMORY)* Разнесение функционала в отдельные файлы ([b76deef](https://github.com/intervisionlord/ANIMA/commit/b76deef9742e9a617b294c51adbf3d8ad2c8a85d))
- *(MEMORY)* Обновлены аннотации ([1e20dcb](https://github.com/intervisionlord/ANIMA/commit/1e20dcbe52953dc9082775d485231fcecf2d489c))
  - Обновлены аннотации
  - Константы вынесены выше

## [0.4.0] — 21.11.2026

### 🚀 Новое

- Инит коммит ([fa3daeb](https://github.com/intervisionlord/ANIMA/commit/fa3daeb50c3ff0c44e23579c6057a37272c7ec3c))

