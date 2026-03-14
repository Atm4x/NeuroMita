from ui.gui_templates import create_settings_section, create_section_header
from utils.translation_manager import t
from main_logger import logger

def get_camera_list():
    try:
        import cv2
        camera_list = []
        for i in range(5):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                camera_list.append(f"Camera {i}")
                cap.release()
        return camera_list if camera_list else [t("ui.settings.screen_analysis.no_cameras")]
    except ImportError as ex:
        logger.warning('OpenCV не установлен: камеры не обнаружены.')
        return [t("ui.settings.screen_analysis.no_cameras")]

def update_camera_list(gui):
    if hasattr(gui, 'camera_combobox'):
        current_text = gui.camera_combobox.currentText()
        gui.camera_combobox.clear()
        new_list = get_camera_list()
        gui.camera_combobox.addItems(new_list)
        if current_text in new_list:
            gui.camera_combobox.setCurrentText(current_text)

def on_camera_selected(gui):
    if hasattr(gui, 'camera_combobox'):
        selection = gui.camera_combobox.currentText()
        if selection and "Camera" in selection:
            try:
                camera_index = int(selection.split(" ")[-1])
                gui.settings.set("CAMERA_INDEX", camera_index)
                logger.info(f"Выбрана камера: {camera_index}")
            except (IndexError, ValueError):
                logger.error(f"Не удалось извлечь индекс из '{selection}'")

def setup_screen_analysis_controls(gui, parent_layout):
    # ОДИН ОБЩИЙ ЗАГОЛОВОК для всех настроек экрана
    create_section_header(parent_layout, t("ui.settings.screen_analysis.title"))

    # Первая CollapsibleSection
    screen_analysis_config = [
        {'label': t('ui.settings.screen_analysis.enable'), 'key': 'ENABLE_SCREEN_ANALYSIS', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': t('ui.settings.screen_analysis.capture_interval'), 'key': 'SCREEN_CAPTURE_INTERVAL', 'type': 'entry', 'default': '5.0', 'validation': gui.validate_float_positive},
        {'label': t('ui.settings.screen_analysis.compression'), 'key': 'SCREEN_CAPTURE_QUALITY', 'type': 'entry', 'default': '25', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.frames_per_second'), 'key': 'SCREEN_CAPTURE_FPS', 'type': 'entry', 'default': '1', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.frames_in_history'), 'key': 'SCREEN_CAPTURE_HISTORY_LIMIT', 'type': 'entry', 'default': '1', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.frames_for_transfer'), 'key': 'SCREEN_CAPTURE_TRANSFER_LIMIT', 'type': 'entry', 'default': '1', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.capture_width'), 'key': 'SCREEN_CAPTURE_WIDTH', 'type': 'entry', 'default': '1024', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.capture_height'), 'key': 'SCREEN_CAPTURE_HEIGHT', 'type': 'entry', 'default': '768', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.send_image_requests'), 'key': 'SEND_IMAGE_REQUESTS', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': t('ui.settings.screen_analysis.request_interval'), 'key': 'IMAGE_REQUEST_INTERVAL', 'type': 'entry', 'depends_on': "SEND_IMAGE_REQUESTS", 'default': '20.0', 'validation': gui.validate_float_positive},
        {'label': t('ui.settings.screen_analysis.exclude_gui_window'), 'key': 'EXCLUDE_GUI_WINDOW', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': t('ui.settings.screen_analysis.excluded_window_title'), 'key': 'EXCLUDE_WINDOW_TITLE', 'type': 'entry', 'default': ''},
    ]
    create_settings_section(gui, parent_layout, t("ui.settings.screen_analysis.section_screen_analysis"), screen_analysis_config)

    # Вторая CollapsibleSection
    camera_analysis_config = [
        {'label': t('ui.settings.screen_analysis.enable_camera'), 'key': 'ENABLE_CAMERA_CAPTURE', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': t('ui.settings.screen_analysis.camera'), 'key': 'CAMERA_DEVICE', 'type': 'combobox', 'options': get_camera_list(), 'default': get_camera_list()[0], 'command': lambda: on_camera_selected(gui), 'widget_name': 'camera_combobox'},
        {'label': t("ui.settings.screen_analysis.refresh_list"), 'type': 'button', 'command': lambda: update_camera_list(gui)},
        {'label': t('ui.settings.screen_analysis.capture_interval'), 'key': 'CAMERA_CAPTURE_INTERVAL', 'type': 'entry', 'default': '5.0', 'validation': gui.validate_float_positive},
        {'label': t('ui.settings.screen_analysis.compression'), 'key': 'CAMERA_CAPTURE_QUALITY', 'type': 'entry', 'default': '25', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.frames_per_second'), 'key': 'CAMERA_CAPTURE_FPS', 'type': 'entry', 'default': '1', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.frames_in_history'), 'key': 'CAMERA_CAPTURE_HISTORY_LIMIT', 'type': 'entry', 'default': '1', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.frames_for_transfer'), 'key': 'CAMERA_CAPTURE_TRANSFER_LIMIT', 'type': 'entry', 'default': '1', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.capture_width'), 'key': 'CAMERA_CAPTURE_WIDTH', 'type': 'entry', 'default': '640', 'validation': gui.validate_positive_integer},
        {'label': t('ui.settings.screen_analysis.capture_height'), 'key': 'CAMERA_CAPTURE_HEIGHT', 'type': 'entry', 'default': '480', 'validation': gui.validate_positive_integer},
    ]
    gui.camera_section = create_settings_section(gui, parent_layout, t("ui.settings.screen_analysis.section_camera"), camera_analysis_config)

    # Третья CollapsibleSection
    frame_compression_config = [
        {'label': t('ui.settings.screen_analysis.enable_frame_regression'), 'key': 'IMAGE_QUALITY_REDUCTION_ENABLED', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': t('ui.settings.screen_analysis.reduction_start_index'), 'key': 'IMAGE_QUALITY_REDUCTION_START_INDEX', 'type': 'entry', 'default': '25', 'validation': gui.validate_positive_integer_or_zero},
        {'label': t('ui.settings.screen_analysis.use_percentage_reduction'), 'key': 'IMAGE_QUALITY_REDUCTION_USE_PERCENTAGE', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': t('ui.settings.screen_analysis.minimum_quality'), 'key': 'IMAGE_QUALITY_REDUCTION_MIN_QUALITY', 'type': 'entry', 'default': '30', 'validation': gui.validate_positive_integer_or_zero},
        {'label': t('ui.settings.screen_analysis.decrease_rate'), 'key': 'IMAGE_QUALITY_REDUCTION_DECREASE_RATE', 'type': 'entry', 'default': '5', 'validation': gui.validate_positive_integer},
    ]
    create_settings_section(gui, parent_layout, t("ui.settings.screen_analysis.section_frame_regression"), frame_compression_config)