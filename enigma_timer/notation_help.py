"""Short, discipline-specific instructions for the shared notation studio."""
import re
from .i18n import pick,tr
from .notation import CUBE_EVENTS

MOVES = {
    "pyram": ("U","L","R","B","u","l","r","b"),
    "skewb": ("R","U","L","B"),
    "minx": ("U","F","R","L","BR","BL","R++","D++"),
    "sq1": ("(1,0)","(0,1)","/"),
    "clock": ("UL","UR","DL","DR","U","R","D","L","ALL","y2"),
}


def grip_text(puzzle):
    texts = {
        "pyram": ("Green face towards you · U vertex up · Bottom face horizontal", "Зелёная грань к себе · Вершина U сверху · Основание горизонтально"),
        "skewb": ("White on top · Green towards you · Turns go around corners", "Белый сверху · Зелёный к себе · Повороты вокруг углов"),
        "minx": ("White on top · Green towards you · For R++ / D++ keep the top-left three pieces still", "Белый сверху · Зелёный к себе · В R++ / D++ удерживай три детали сверху слева"),
        "sq1": ("White on top · Small equatorial surface at the front-left · / turns the right half", "Белый сверху · Узкая часть пояса слева спереди · / поворачивает правую половину"),
        "clock": ("12 o’clock up · Light face towards you · y2 turns the puzzle over", "12 часов сверху · Светлая сторона к себе · y2 переворачивает головоломку"),
    }
    return pick(texts[puzzle]) if puzzle in texts else tr("notation_grip_short")


def card_name(puzzle,base):
    if puzzle in CUBE_EVENTS:
        return tr("notation_name_"+base)
    if puzzle=="pyram":
        name = {"U":("Top","Верх"),"L":("Left","Лево"),"R":("Right","Право"),"B":("Back","Сзади")}[base.upper()]
        return pick(("Tip "+base.upper(),"Кончик "+base.upper())) if base.islower() else pick(name)
    if puzzle=="skewb":
        return pick({"R":("Back right","Сзади справа"),"U":("Back left","Сзади слева"),"L":("Front left","Спереди слева"),"B":("Bottom back","Снизу сзади")}[base])
    if puzzle=="minx":
        return pick({"R++":("Vertical","Вертикально"),"D++":("Horizontal","Горизонтально"),"BR":("Back right","Сзади справа"),"BL":("Back left","Сзади слева")}[base]) if base in ("R++","D++","BR","BL") else tr("notation_name_"+base)
    if puzzle=="sq1":
        return pick({"(1,0)":("Top","Верх"),"(0,1)":("Bottom","Низ"),"/":("Right half","Правая половина")}[base])
    return pick({"UL":("Upper left","Верхний левый"),"UR":("Upper right","Верхний правый"),"DL":("Lower left","Нижний левый"),"DR":("Lower right","Нижний правый"),"U":("Upper pair","Верхняя пара"),"R":("Right pair","Правая пара"),"D":("Lower pair","Нижняя пара"),"L":("Left pair","Левая пара"),"ALL":("All pins","Все штырьки"),"y2":("Turn over","Перевернуть")}[base])


def move_text(puzzle,move):
    if puzzle in CUBE_EVENTS:
        from .cube import _MOVE_RE
        match = _MOVE_RE.fullmatch(move)
        if match:
            prefix,face,wide,suffix = match.groups()
            angle = 180 if "2" in suffix else 90
            direction = pick(("counter-clockwise","против часовой")) if "'" in suffix and angle!=180 else pick(("clockwise","по часовой"))
            if face in "xyz":
                equivalent = dict(x="R",y="U",z="F")[face]
                return pick((f"Rotate the whole cube {angle}° {direction}, in the direction of {equivalent}.",f"Поверни весь куб на {angle}° {direction}, в направлении хода {equivalent}."))
            if face in "MES":
                equivalent = dict(M="L",E="D",S="F")[face]
                return pick((f"Turn the middle layer {angle}° {direction}, in the direction of {equivalent}. Keep the outer faces still.",f"Поверни средний слой на {angle}° {direction}, в направлении хода {equivalent}. Внешние грани остаются на месте."))
            if prefix or wide or face.islower():
                width = int(prefix) if prefix else 2
                name = tr("notation_name_"+face.upper()).lower()
                if prefix and not wide and face.isupper():
                    return pick((f"Turn only layer {width}, counting from the {name} face, {angle}° {direction}.",f"Поверни только слой №{width}, считая от грани «{name}», на {angle}° {direction}."))
                return pick((f"Turn {width} layers together from the {name} side, {angle}° {direction}.",f"Поверни вместе {width} слоя со стороны «{name}» на {angle}° {direction}."))
        from .assistant import move_description
        return move_description(move)
    inverse = move.endswith("'") or move.endswith("--")
    direction = pick(("counter-clockwise","против часовой")) if inverse else pick(("clockwise","по часовой"))
    if puzzle in ("pyram","skewb"):
        corner = card_name(puzzle,move[0].upper()).lower()
        if puzzle=="skewb":
            corner = pick({"R":("lower back-right","нижний задний правый"),"U":("upper back-left","верхний задний левый"),"L":("lower front-left","нижний передний левый"),"B":("lower back-left","нижний задний левый")}[move[0]])
        if puzzle=="pyram" and move[0].islower():
            return pick((f"Turn only the {corner} 120° {direction}. The two lower layers stay still.",f"Поверни только кончик «{corner}» на 120° {direction}. Нижние два слоя остаются на месте."))
        return pick((f"Look straight at the {corner} vertex and turn its layer 120° {direction}.",f"Смотри прямо на угол «{corner}» и поверни его слой на 120° {direction}."))
    if puzzle=="minx":
        if move.startswith("y"):
            return pick(("Rotate the entire Megaminx around its upper face axis by 72° per step.","Поверни весь Мегаминкс вокруг оси верхней грани: один шаг — 72°."))
        if move.endswith(("++","--")):
            return pick((f"Keep the three top-left pieces still. Turn the rest 144° {direction} using the {card_name(puzzle,move[:1]+'++').lower()} layers.",f"Удерживай три детали сверху слева. Поверни остальную часть на 144° {direction}: {card_name(puzzle,move[:1]+'++').lower()}."))
        angle = 144 if "2" in move else 72
        return pick((f"Look straight at face {move.rstrip(chr(39)).rstrip('2')}. Turn it {angle}° {direction}.",f"Смотри прямо на грань {move.rstrip(chr(39)).rstrip('2')}. Поверни её на {angle}° {direction}."))
    if puzzle=="sq1":
        if move=="/":
            return pick(("Turn the right half 180°. Both cut lines must be clear of corners before a slice.","Поверни правую половину на 180°. Перед слайсом обе линии разреза должны проходить между деталями."))
        top,bottom = map(int,re.findall(r"-?\d+",move))
        return pick((f"Top: {top} × 30°. Bottom: {bottom} × 30°. Positive is clockwise when looking at that layer.",f"Верх: {top} × 30°. Низ: {bottom} × 30°. Плюс — по часовой, если смотреть прямо на этот слой."))
    if move=="y2":
        return pick(("Turn the puzzle over so 12 o’clock stays at the top. Continue on the other face.","Переверни головоломку, сохраняя 12 часов сверху. Дальше работай с другой стороной."))
    match = re.fullmatch(r"(ALL|UR|UL|DR|DL|[URDL])(\d+)([+-])",move)
    if match:
        name,hours,sign = match.groups()
        direction = pick(("clockwise","по часовой")) if sign=="+" else pick(("counter-clockwise","против часовой"))
        unit = "hour" if hours=="1" else "hours"
        return pick((f"Raise pins {name}. Turn a wheel by {hours} {unit} {direction}, then push all pins down.",f"Подними штырьки {name}. Поверни колесо на {hours} ч. {direction}, затем опусти все штырьки."))
    return move
