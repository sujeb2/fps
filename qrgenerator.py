import qrcode, os

TEMP_DIR = 'assets/temp_qrcode'

class QRCode():
    def __init__(self):
        super().__init__()
        if not os.path.isdir(TEMP_DIR):
            print('qrcode: cannot find temp qrcode save location generating.')
            os.makedirs(TEMP_DIR)
        for leftover in os.listdir(TEMP_DIR): # from last run
            self.remove(os.path.join(TEMP_DIR, leftover))

    def generate(self, data: str, name: str): # returns saved qrcode image path
        instance = qrcode.QRCode(
            version=None, # fit to data length
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        instance.add_data(data)
        instance.make(fit=True)
        path = os.path.join(TEMP_DIR, f'{name}.png')
        instance.make_image(fill_color='black', back_color='white').save(path)
        print(f'qrcode: generated with data: {data}, (generated path: {path})')
        return path

    def remove(self, path: str):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
