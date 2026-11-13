import io, re, time
from PIL import Image, ImageOps

MAX_IMAGE_SIDE = 1280 # phone photos are too big for cpu ocr
NAME_LABELS = ('성명', '이름', '학생')
HANGUL_NAME = re.compile(r'^[가-힣]{2,5}$')

class CardReader:
    def __init__(self):
        super().__init__()
        import easyocr # heavy (torch), only loaded by the api server
        print('ocr: loading korean model (first run downloads it)')
        self.reader = easyocr.Reader(['ko', 'en'], gpu=False)
        print('ocr: ready')

    def readText(self, image_bytes: bytes):
        import numpy
        start = time.time()
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert('RGB') # phone rotation
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        texts = self.reader.readtext(numpy.array(image), detail=0) # no rotation_info, it doubles the time
        print(f'ocr: read {len(texts)} texts in {time.time() - start:.1f}s')
        return texts

def nameCandidates(texts: list[str]): # korean name-like texts on the student card
    candidates = []
    def add(text):
        text = text.replace(':', '')
        for label in NAME_LABELS:
            if text.startswith(label):
                text = text[len(label):]
        if HANGUL_NAME.match(text) and text not in candidates:
            candidates.append(text)

    letters = '' # wide letter spaced name read as single letters ("강", "성", "은")
    for text in texts:
        add(''.join(text.split())) # spaced name like "홍 길 동"
        for word in text.split(): # name inside a longer line like "성명 홍길동 2학년"
            add(word)
        word = ''.join(text.split())
        if len(word) == 1:
            letters += word
            continue
        add(letters)
        letters = ''
    add(letters)
    return candidates
