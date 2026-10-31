# Настройки: изменения, подписки и сохранение

**Capability:** CAP-CONFIG-001. **Статус:** ACTIVE. SettingsManager владеет SettingsRegistry и асинхронным JSON writer; SettingsService предоставляет тот же source of truth для GUI/core. Проверялись исходники, содержимое пользовательских settings не читалось.

Приложение умеет читать/менять значения, batch update, snapshot/revision, подписаться на выбранные keys с optional replay, перечитать файл и сохранить при shutdown. Defaults преимущественно задаются consumers, не единым обязательным typed schema. Registry хранит произвольные Python values; equality подавляет неизменившееся set, каждый изменённый key повышает revision и создаёт SettingChange(key/value/previous/revision/source).

Подписки исполняются асинхронно через SerialDispatcher: отдельно упорядочены по listener token, разные listeners могут работать параллельно. Listener получает backlog deque; ошибки логируются, остальные listeners продолжаются. Update_many меняет все values под lock, но публикует отдельные key changes; subscriber, читая registry, может видеть уже весь batch. Freeze dataclass не делает вложенные values immutable: snapshot/get/change используют shallow values без deepcopy. In-place изменение вложенного dict/list может обойти revision/notification/persistence scheduling. Это требование к новой модели конфигурации.

Set подтверждает изменение памяти, не durable commit. Save/save_settings лишь кладёт marker в очередь ёмкостью1; writer дебаунсит0.5 s, берёт актуальный snapshot, пишет tmp+flush/fsync+replace. Ошибка пишется в log, per-setting failure UI не получает. Shutdown пытается завершить writer и отдельно пишет final snapshot; реальная file failure не отменяет уже применённые runtime effects. После загрузки повреждённого JSON делается corrupt backup и используются defaults; не-JSON IO failure также даёт пустое состояние с log. Невалидный JSON root возвращает пустой dict.

Load_settings replace_all(notify=False) меняет registry без уведомления runtime consumers, кроме отдельно выполненной migration. Fallback static get до initialization читает файл и кеширует по path/mtime, а set до initialization возвращает False. Чтение этой fallback ветви не означает существование готового SettingsManager.

Пользовательские настройки, API preset credentials, OAuth protected accounts, ASR/model profiles и installer journals — разные stores. Общий JSON настроек не обеспечивает secret protection; HIDE_PRIVATE — UI mask. Конкретные конфигурационные migration/import/export paths и полный список всех файлов ещё проверяются; нельзя считать эту страницу полным data inventory.

Новой реализации нужны типы/validation/defaults/migrations для параметров, immutable/versioned snapshots, batch semantics и разделённые applied/durably saved outcomes. Reactive settings меняют доступность функций сразу либо после restart по явной policy. Source of truth не обязан быть глобальным singleton/flat dict, а fsync replace сам по себе не делает атомарной настройку связанных subsystems.

Источники: SettingsManager read/load/write/debounce/shutdown целиком; SettingsRegistry set/update_many/replace/snapshot/subscribe/dispatch/close; SettingsManagerService и функциональные consumers. Mapping compatibility хвост и низкоуровневый SerialDispatcher отдельно не закрыты полностью; тестов с настоящими settings не было.
