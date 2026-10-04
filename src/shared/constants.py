"""
常量定义模块，用于存储应用程序中使用的各种常量
"""
import os
from src.shared.prompt_defaults import get_prompt_factory_defaults
from src.shared.text_style_defaults import (
    get_text_style_factory_defaults,
)


_TEXT_STYLE_DEFAULTS = get_text_style_factory_defaults()

DEFAULT_FONT_RELATIVE_PATH = os.path.join(
    "src",
    "backend_v2",
    "resources",
    _TEXT_STYLE_DEFAULTS["fontFamily"].replace("/", os.sep),
)
DEFAULT_FONT_FAMILY = _TEXT_STYLE_DEFAULTS["fontFamily"]
DEFAULT_FONT_SIZE = _TEXT_STYLE_DEFAULTS["fontSize"]
_layout_direction = _TEXT_STYLE_DEFAULTS["layoutDirection"]
DEFAULT_TEXT_DIRECTION = (
    _layout_direction
    if _layout_direction in {"vertical", "horizontal"}
    else "vertical"
)
DEFAULT_TEXT_COLOR = _TEXT_STYLE_DEFAULTS["textColor"]
DEFAULT_FILL_COLOR = _TEXT_STYLE_DEFAULTS["fillColor"]
DEFAULT_INPAINT_METHOD = _TEXT_STYLE_DEFAULTS["inpaintMethod"]
DEFAULT_LINE_SPACING = _TEXT_STYLE_DEFAULTS["lineSpacing"]
DEFAULT_INLINE_ALIGN = _TEXT_STYLE_DEFAULTS["inlineAlign"]
DEFAULT_BLOCK_ALIGN = _TEXT_STYLE_DEFAULTS["blockAlign"]
DEFAULT_STROKE_ENABLED = _TEXT_STYLE_DEFAULTS["strokeEnabled"]
DEFAULT_STROKE_COLOR = _TEXT_STYLE_DEFAULTS["strokeColor"]
DEFAULT_STROKE_WIDTH = _TEXT_STYLE_DEFAULTS["strokeWidth"]

_PROMPT_FACTORY_DEFAULTS = get_prompt_factory_defaults()

DEFAULT_PROMPT = _PROMPT_FACTORY_DEFAULTS["singleNormal"]
DEFAULT_TRANSLATE_JSON_PROMPT = _PROMPT_FACTORY_DEFAULTS["singleJson"]
BATCH_TRANSLATE_SYSTEM_TEMPLATE = _PROMPT_FACTORY_DEFAULTS["batchNormal"]
BATCH_TRANSLATE_JSON_SYSTEM_TEMPLATE = _PROMPT_FACTORY_DEFAULTS["batchJson"]
DEFAULT_HQ_TRANSLATE_PROMPT = _PROMPT_FACTORY_DEFAULTS["hqTranslation"]
DEFAULT_PROOFREADING_PROMPT = _PROMPT_FACTORY_DEFAULTS["proofreading"]
DEFAULT_AI_VISION_OCR_PROMPT = _PROMPT_FACTORY_DEFAULTS["aiVisionOcrNormal"]
DEFAULT_AI_VISION_OCR_JSON_PROMPT = _PROMPT_FACTORY_DEFAULTS["aiVisionOcrJson"]
DEFAULT_WEB_IMPORT_EXTRACTION_PROMPT = _PROMPT_FACTORY_DEFAULTS[
    "webImportExtraction"
]

# 批量翻译的用户提示词模板
BATCH_TRANSLATE_USER_TEMPLATE = '''请帮我将以下漫画文本翻译成中文。如果文本已经是中文或者看起来是拟声词/音效词，请原样输出。保持编号前缀格式。
'''

# 批量翻译的示例（用于 few-shot learning）
BATCH_TRANSLATE_SAMPLE_INPUT = (
    '<|1|>恥ずかしい… 目立ちたくない… 私が消えたい…\n'
    '<|2|>きみ… 大丈夫⁉\n'
    '<|3|>なんだこいつ 空気読めて ないのか…？'
)
BATCH_TRANSLATE_SAMPLE_OUTPUT = (
    '<|1|>好尴尬…我不想引人注目…我想消失…\n'
    '<|2|>你…没事吧⁉\n'
    '<|3|>这家伙怎么看不懂气氛的…？'
)

# JSON 模式的用户提示词
BATCH_TRANSLATE_JSON_USER_TEMPLATE = '''请帮我将以下漫画文本翻译成中文，严格按照 JSON 格式输出。
'''

# JSON 模式的示例（用于 few-shot learning）
BATCH_TRANSLATE_JSON_SAMPLE_INPUT = '''{
  "texts": [
    {"id": 1, "text": "恥ずかしい… 目立ちたくない… 私が消えたい…"},
    {"id": 2, "text": "きみ… 大丈夫⁉"},
    {"id": 3, "text": "なんだこいつ 空気読めて ないのか…？"}
  ]
}'''

BATCH_TRANSLATE_JSON_SAMPLE_OUTPUT = '''{
  "translations": [
    {"id": 1, "text": "好尴尬…我不想引人注目…我想消失…"},
    {"id": 2, "text": "你…没事吧⁉"},
    {"id": 3, "text": "这家伙怎么看不懂气氛的…？"}
  ]
}'''

# --- 翻译服务相关 ---
# 百度翻译API引擎ID
BAIDU_TRANSLATE_ENGINE_ID = 'baidu_translate'
# 有道翻译API引擎ID
YOUDAO_TRANSLATE_ENGINE_ID = 'youdao_translate'

# --- 文件与目录 ---
# 默认字体路径指向 v2 只读资源目录。
# 注意：
# - 内置字体随应用发布，位于 src/backend_v2/resources/fonts/
# - 用户上传字体进入 v2 对象存储，不修改应用资源目录

# --- 默认渲染参数 ---
DEFAULT_ROTATION_ANGLE = 0
# DEFAULT_FONT_SIZE / DEFAULT_TEXT_DIRECTION / DEFAULT_TEXT_COLOR /
# DEFAULT_FILL_COLOR / DEFAULT_INPAINT_METHOD / DEFAULT_LINE_SPACING /
# DEFAULT_INLINE_ALIGN / DEFAULT_BLOCK_ALIGN 在模块顶部由工厂资源初始化

# --- 百度翻译相关 ---
# 项目内部语言代码到百度翻译语言代码的映射
PROJECT_TO_BAIDU_TRANSLATE_LANG_MAP = {
    'zh': 'zh',
    'en': 'en',
    'japan': 'jp',
    'korean': 'kor',
    'chinese': 'zh',
    'chinese_cht': 'zh',
    'french': 'fra',
    'german': 'de',
    'russian': 'ru',
    'italian': 'it',
    'spanish': 'spa'
}

# --- AI 视觉 OCR 相关 ---
AI_VISION_OCR_ENGINE_ID = 'ai_vision'  # 定义唯一标识符

# --- 有道翻译相关 ---
# 项目内部语言代码到有道翻译语言代码的映射
PROJECT_TO_YOUDAO_TRANSLATE_LANG_MAP = {
    'zh': 'zh-CHS',
    'en': 'en',
    'japan': 'ja',
    'korean': 'ko',
    'chinese': 'zh-CHS',
    'chinese_cht': 'zh-TW',
    'french': 'fr',
    'german': 'de',
    'russian': 'ru',
    'italian': 'it',
    'spanish': 'es'
}

# --- rpm (Requests Per Minute) Limiting ---
DEFAULT_rpm_TRANSLATION = 0  # 0 表示无限制
DEFAULT_rpm_AI_VISION_OCR = 0 # 0 表示无限制

# --- AI Vision OCR 图片尺寸限制 ---
DEFAULT_AI_VISION_MIN_IMAGE_SIZE = 32  # VLM 模型通常要求 >= 28px

# --- 文本描边 ---
# DEFAULT_STROKE_ENABLED / DEFAULT_STROKE_COLOR / DEFAULT_STROKE_WIDTH
# 在模块顶部由工厂资源初始化

# --- 48px OCR 相关 ---
OCR_ENGINE_48PX = '48px_ocr'
MODEL_48PX_DIR = 'models/ocr_48px'
MODEL_48PX_CHECKPOINT = 'ocr_ar_48px.ckpt'
MODEL_48PX_DICT = 'alphabet-all-v7.txt'

# --- Paddle OCR / PaddleOCR-VL 相关 ---
PADDLE_OCR_VERSION = 'PP-OCRv6'
PADDLE_OCR_MODEL_TIER = 'medium'
PADDLE_OCR_MODEL_DIR = 'models/paddle_ocr_onnx_v6'

OCR_ENGINE_PADDLEOCR_VL = 'paddleocr_vl'
PADDLEOCR_VL_VERSION = 'PaddleOCR-VL-1.6'
PADDLEOCR_VL_MODEL_DIR = 'models/paddleocr_vl_1_6'

# CTD 配置
# 边缘距离比例阈值：当一个文本行与多个邻居连接时，如果到某个邻居的距离
# 远大于到最近邻居的距离 (比例超过此阈值)，则断开这个连接，防止跨气泡错误合并
# 推荐值 3.0-5.0，0 表示禁用
CTD_EDGE_RATIO_THRESHOLD = 0.0

# 气泡感知合并：利用气泡描边把相邻气泡的文本行分开，防止"两个气泡被识别成一个"
ENABLE_BUBBLE_AWARE_MERGE = True

# Default(DBNet) 检测器漏检补救：在同一张概率图上用更低阈值补回浅色/小字号文本行。
# 不增加模型推理次数。阈值设为 0 可关闭。
DEFAULT_DETECTOR_RESCUE_THRESHOLD = 0.3
DEFAULT_DETECTOR_RESCUE_MIN_SCORE = 0.42

# 智能纯色填充：逐气泡采样底色、去除文字抗锯齿残影、图上文字改用局部修复
SMART_SOLID_FILL = True

# MangaOCR 漏字重試：整個氣泡一次識別的字數明顯少於文字行面積估算的字數時，
# 改為每次 2 列（行）分段識別再拼接。比例設為 0 可關閉。
MANGA_OCR_CHUNK_RETRY_RATIO = 0.6
MANGA_OCR_CHUNK_LINES = 2

# LaMa 分區域修復時，周圍是純色（白色氣泡等）的區域直接用周圍顏色填充，
# 不跑模型：更快，也不會在白底上留下灰色污漬。數值是允許的周圍顏色標準差。
LAMA_FLAT_FILL_MAX_STD = 6.0

# 自動文字顏色：直接量測原圖文字像素（比 48px 模型推測更準、也不需要再跑模型）
PIXEL_TEXT_COLOR = True

# 譯文以 N 倍解析度繪製後縮回（超取樣）。FreeType 本身已有抗鋸齒，
# 縮回時還會重新取樣文字周圍的背景，反而偏糊，因此預設關閉（1）。
# 字更清晰改由 IMPORT_UPSCALE_* 在匯入時放大小圖達成。
TEXT_SUPERSAMPLE = 1

# 匯入時放大小圖：長邊小於此像素的頁面先放大 2 倍再處理，
# 偵測、去字、嵌字都在高解析度進行，譯文字更銳利。0 = 關閉。
IMPORT_UPSCALE_BELOW = 1600
IMPORT_UPSCALE_FACTOR = 2

# 去字遮罩膨胀隨頁面尺寸放大（以 1500px 長邊為基準）
ADAPTIVE_MASK_DILATE = True
# 去字後清除純色氣泡內殘留的小點（灰點、彩點、白點）
REPAIR_DESPECKLE = True
# 去字後二次修復：清掉黏在修復區外緣的白邊、彩色描邊殘留（網點、畫面上也有效）
REPAIR_RESIDUE_CLEANUP = True

# MangaOCR 加強：每次讀取都算信心分數（平均 token 對數機率），低於門檻就用整理過的圖
# （留白、對比、二值化去網點、小字放大）與 beam search 重讀，取最有把握的結果
MANGA_OCR_ENHANCE = True
MANGA_OCR_CONFIDENT_SCORE = -0.12
MANGA_OCR_BEAMS = 4

# 翻譯時附上 OCR 錯字還原規則（形近漢字、假名），讓模型依上下文修正辨識錯誤
OCR_CORRECTION_IN_PROMPT = True

# 排版方向依整頁判斷：只讓明顯細長（長寬比 ≥ DIRECTION_CONFIDENT_ASPECT）的文字行投票，
# 接近正方形的短字（あっ、♡）跟隨整頁主要方向；整頁無法判斷時用預設（日漫直排）
PAGE_AWARE_TEXT_DIRECTION = True
DIRECTION_CONFIDENT_ASPECT = 1.5
DEFAULT_PAGE_TEXT_DIRECTION = 'v'

# 自動字號不超過原文字號（由文字行寬度估算），讓譯文大小和原圖一致
MATCH_SOURCE_FONT_SIZE = True

# 辅助一阶段 YSGYolo 检测配置
ENABLE_AUX_YOLO_DETECTION = False
AUX_YOLO_CONF_THRESHOLD = 0.4
AUX_YOLO_OVERLAP_THRESHOLD = 0.1

# SaberYOLO 配置（二阶段误合并纠错）
SABER_YOLO_MODEL_DIR = 'models/saber_yolo'
SABER_YOLO_MODEL_NAME = 'saber_yolo.pt'
SABER_YOLO_CONF_THRESH = 0.2
SABER_YOLO_IOU_THRESH = 0.5
ENABLE_SABER_YOLO_REFINE = True
SABER_YOLO_REFINE_OVERLAP_THRESHOLD = 0.5

# --- 重试机制设置 ---
DEFAULT_TRANSLATION_MAX_RETRIES = 3  # 普通翻译默认重试次数

# --- 超长图片处理 (Large Image Rearrange) ---
LARGE_IMAGE_ENABLED = True  # 是否启用超长图片自动切割
LARGE_IMAGE_TARGET_SIZE = 1536  # 切片目标尺寸（与检测器一致）
