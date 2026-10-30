from dataclasses import dataclass, field

from algorithms import contrast, morphology, pointwise, structuring
from core.explain import EXPLAIN
from memory.buffer import BORDER_NAMES


@dataclass
class Param:
    key: str
    label: str
    kind: str
    default: object = None
    low: float = 0
    high: float = 1
    step: float = 1
    choices: list = field(default_factory=list)
    only: dict = field(default_factory=dict)


@dataclass
class Method:
    key: str
    title: str
    params: list
    explanation: str
    run: object


class NeedSecondImage(Exception):
    pass


POINT_OPERATIONS = [
    ("negative", "Негатив"),
    ("brightness", "Сдвиг яркости"),
    ("contrast", "Контраст (вокруг середины)"),
    ("linear", "Линейное преобразование a·x + b"),
    ("gamma", "Гамма-коррекция"),
    ("log", "Логарифмическое преобразование"),
    ("exp", "Экспоненциальное преобразование"),
    ("threshold", "Бинаризация по порогу"),
    ("solarize", "Соляризация"),
    ("posterize", "Постеризация"),
]

PAIR_OPERATIONS = [
    ("sum", "Сумма"),
    ("difference", "Разность A - B"),
    ("absdiff", "Модуль разности |A - B|"),
    ("product", "Произведение"),
    ("average", "Среднее"),
    ("blend", "Смешивание α·A + (1-α)·B"),
    ("min", "Минимум"),
    ("max", "Максимум"),
    ("and", "Побитовое И"),
    ("or", "Побитовое ИЛИ"),
    ("xor", "Побитовое исключающее ИЛИ"),
]

CONTRAST_MODES = [
    ("all", "Общее окно для всех каналов"),
    ("channels", "Отдельно по каналам RGB"),
    ("value", "По яркости V (HSV)"),
    ("manual", "Ручное окно [min; max]"),
]

EQUALIZE_MODES = [
    ("rgb", "Эквализация по каналам RGB"),
    ("value", "Эквализация яркости V (HSV)"),
    ("clahe", "CLAHE по яркости V (HSV)"),
]

COLOR_MODES = [
    ("channels", "Каждый канал RGB отдельно"),
    ("value", "Только яркость V (HSV)"),
]


def key_of(choices, title):
    for key, name in choices:
        if name == title:
            return key
    return choices[0][0]


def run_point(buffer, values, context):
    operation = key_of(POINT_OPERATIONS, values["operation"])
    builders = {
        "negative": lambda: pointwise.negative_lut(),
        "brightness": lambda: pointwise.brightness_lut(values["shift"]),
        "contrast": lambda: pointwise.contrast_lut(values["gain"]),
        "linear": lambda: pointwise.linear_lut(values["gain"], values["shift"]),
        "gamma": lambda: pointwise.gamma_lut(values["gamma"]),
        "log": lambda: pointwise.log_lut(values["strength"]),
        "exp": lambda: pointwise.exp_lut(values["strength"]),
        "threshold": lambda: pointwise.threshold_lut(values["threshold"]),
        "solarize": lambda: pointwise.solarize_lut(values["threshold"]),
        "posterize": lambda: pointwise.posterize_lut(int(values["levels"])),
    }
    lut = builders[operation]()
    return pointwise.apply_lut(buffer, lut, context.job, context.workers), "таблица замены из 256 значений"


def run_pair(buffer, values, context):
    if context.second is None:
        raise NeedSecondImage("Загрузите второе изображение кнопкой «Второе изображение…»")
    operation = key_of(PAIR_OPERATIONS, values["operation"])
    result = pointwise.combine(buffer, context.second, operation, values["alpha"], context.job, context.workers)
    return result, "второе изображение приведено к размеру первого"


def run_contrast(buffer, values, context):
    mode = key_of(CONTRAST_MODES, values["mode"])
    return contrast.linear_contrast(
        buffer, mode, values["percent"], int(values["low"]), int(values["high"]), context.job, context.workers)


def run_equalize(buffer, values, context):
    mode = key_of(EQUALIZE_MODES, values["mode"])
    if mode == "clahe":
        result = contrast.clahe(buffer, int(values["tiles"]), values["clip"], context.job, context.workers)
        return result, f"сетка {int(values['tiles'])}×{int(values['tiles'])}, предел контраста {values['clip']:.1f}"
    return contrast.equalize(buffer, mode, context.job, context.workers), "по гистограмме и функции распределения"


def run_morphology(buffer, values, context):
    shape = values["shape"]
    element = structuring.make_element(shape, values["width"], values["height"], values["matrix"])
    operation = next(key for key, name in morphology.OPERATIONS.items() if name == values["operation"])
    border = next(key for key, name in BORDER_NAMES.items() if name == values["border"])
    color_mode = key_of(COLOR_MODES, values["color"])
    result, note = morphology.morphology(
        buffer, operation, element, int(values["iterations"]), border, color_mode,
        bool(values["binarize"]), int(values["threshold"]), context.job, context.workers)
    size = f"структурирующий элемент {element.shape[1]}×{element.shape[0]}, единиц: {int(element.sum())}"
    return result, size + ("; " + note if note else "")


def build_methods():
    point_names = [name for _, name in POINT_OPERATIONS]
    only = lambda *keys: {"operation": [name for key, name in POINT_OPERATIONS if key in keys]}
    return [
        Method(
            "point", "Поэлементные операции",
            [
                Param("operation", "Операция", "choice", point_names[0], choices=point_names),
                Param("shift", "Сдвиг b", "scale", 40, -255, 255, 1, only=only("brightness", "linear")),
                Param("gain", "Коэффициент a", "scale", 1.5, 0.1, 5.0, 0.05, only=only("contrast", "linear")),
                Param("gamma", "Гамма γ", "scale", 0.6, 0.1, 5.0, 0.05, only=only("gamma")),
                Param("strength", "Сила c", "scale", 2.0, 0.1, 10.0, 0.1, only=only("log", "exp")),
                Param("threshold", "Порог T", "scale", 128, 0, 255, 1, only=only("threshold", "solarize")),
                Param("levels", "Число уровней", "scale", 4, 2, 16, 1, only=only("posterize")),
            ],
            EXPLAIN["point"], run_point),
        Method(
            "pair", "Операции с двумя изображениями",
            [
                Param("operation", "Операция", "choice", PAIR_OPERATIONS[0][1], choices=[n for _, n in PAIR_OPERATIONS]),
                Param("alpha", "Вес α первого", "scale", 0.5, 0.0, 1.0, 0.05,
                      only={"operation": [PAIR_OPERATIONS[5][1]]}),
            ],
            EXPLAIN["pair"], run_pair),
        Method(
            "contrast", "Линейное контрастирование",
            [
                Param("mode", "Режим", "choice", CONTRAST_MODES[0][1], choices=[n for _, n in CONTRAST_MODES]),
                Param("percent", "Отсечение краёв, %", "scale", 0.0, 0.0, 20.0, 0.5,
                      only={"mode": [n for k, n in CONTRAST_MODES if k != "manual"]}),
                Param("low", "Нижняя граница", "scale", 40, 0, 254, 1, only={"mode": [CONTRAST_MODES[3][1]]}),
                Param("high", "Верхняя граница", "scale", 200, 1, 255, 1, only={"mode": [CONTRAST_MODES[3][1]]}),
            ],
            EXPLAIN["contrast"], run_contrast),
        Method(
            "equalize", "Эквализация и CLAHE",
            [
                Param("mode", "Метод", "choice", EQUALIZE_MODES[0][1], choices=[n for _, n in EQUALIZE_MODES]),
                Param("clip", "Предел контраста", "scale", 3.0, 1.0, 20.0, 0.5, only={"mode": [EQUALIZE_MODES[2][1]]}),
                Param("tiles", "Плиток по стороне", "scale", 8, 2, 32, 1, only={"mode": [EQUALIZE_MODES[2][1]]}),
            ],
            EXPLAIN["equalize"], run_equalize),
        Method(
            "morphology", "Морфологическая обработка",
            [
                Param("operation", "Операция", "choice", list(morphology.OPERATIONS.values())[0],
                      choices=list(morphology.OPERATIONS.values())),
                Param("shape", "Форма элемента", "choice", structuring.SHAPES[1], choices=structuring.SHAPES),
                Param("width", "Ширина", "scale", 5, 1, 61, 1,
                      only={"shape": [s for s in structuring.SHAPES if s != "Своя матрица"]}),
                Param("height", "Высота", "scale", 5, 1, 61, 1,
                      only={"shape": [s for s in structuring.SHAPES if s not in ("Своя матрица", "Горизонтальная линия")]}),
                Param("matrix", "Матрица 0/1 (строки через /)", "text", "0 1 0/1 1 1/0 1 0",
                      only={"shape": ["Своя матрица"]}),
                Param("iterations", "Повторов", "scale", 1, 1, 10, 1),
                Param("border", "Края изображения", "choice", list(BORDER_NAMES.values())[0],
                      choices=list(BORDER_NAMES.values())),
                Param("color", "Цветное изображение", "choice", COLOR_MODES[0][1], choices=[n for _, n in COLOR_MODES]),
                Param("binarize", "Сначала бинаризовать", "check", False),
                Param("threshold", "Порог (0 = метод Оцу)", "scale", 0, 0, 255, 1, only={"binarize": [True]}),
            ],
            EXPLAIN["morphology"], run_morphology),
    ]
