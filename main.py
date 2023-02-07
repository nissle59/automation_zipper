import os
import zipfile
import urllib.request
from urllib.parse import urlparse
import csv
import ftplib
import configparser


class Item:
    exe_name: str
    exe_link: str
    src_folder_name: str
    dst_folder_name: str
    arc_name: str

    def __init__(self, arc_name, exe_name, src_folder_name, dst_folder_name, exe_link):
        self.exe_name = exe_name
        self.arc_name = arc_name
        self.src_folder_name = src_folder_name
        self.dst_folder_name = dst_folder_name
        self.exe_link = exe_link


FTP_HOST = ''
FTP_USER = ''
FTP_PASS = ''
FTP_PORT = 21
FTP_PATH = ''


def load_config(cfg_file):
    global FTP_HOST, FTP_USER, FTP_PASS, FTP_PORT, FTP_PATH
    config = configparser.ConfigParser()  # создаём объекта парсера
    config.read(cfg_file)  # читаем конфиг
    FTP_HOST = config["FTP"]["host"]
    FTP_PORT = int(config["FTP"]["port"])
    FTP_PATH = config["FTP"]["path"]
    FTP_USER = config["FTP"]["user"]
    FTP_PASS = config["FTP"]["pass"]


def find(name, path='./'):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(name)


def get_filesize_by_url(url):
    site = urllib.request.urlopen(url)
    cl = site.headers.get("Content-Length")
    return int(cl)


def load_list(csv_file):
    items = []
    with open(csv_file, newline='') as csvfile:
        sreader = csv.reader(csvfile, delimiter=';', quotechar='|')
        i = 0
        for row in sreader:
            if i > 0:
                buf = Item(row[0], row[1], row[2], row[3], row[4])
                items.append(buf)
            i += 1
    return items


def zipdir(path, arc_root, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file),
                       os.path.relpath(os.path.join(arc_root, file),
                                       os.path.join(path, '..')))


def ftp_upload(ftp_obj, path):
    with open(path, 'rb') as fobj:
        ftp_obj.storbinary('STOR ' + path, fobj, 1024)


def send_file(host, fname, user, password, port=21):
    os.chdir('out')
    try:
        ftp = ftplib.FTP(host=host)
        ftp.connect(port=port)
        ftp.login(user=user, passwd=password)
        if FTP_PATH != '':
            ftp.cwd(FTP_PATH)
        ftp_upload(ftp, fname)
        ftp.quit()
    except:
        print('Cant send file to FTP')
        try:
            os.remove(fname)
        except:
            print(f'Cant remove {fname}')
    os.chdir('..')


def compress(i: Item):
    remote_size = get_filesize_by_url(i.exe_link)
    print(f'Processing {i.arc_name}...')
    fname = urlparse(i.exe_link).path.split('/')[-1]
    if find(f'{i.arc_name}.zip', 'out'):
        with zipfile.ZipFile(f'out/{i.arc_name}.zip', 'a', zipfile.ZIP_DEFLATED) as zipf:
            ef = False
            try:
                l_zip_size = zipf.getinfo(f'{i.exe_name}.exe').file_size
                if remote_size != l_zip_size:
                    ef = True
            except:
                ef = True
            if ef:
                print(f'Loading {fname} of {i.arc_name}...')
                urllib.request.urlretrieve(i.exe_link, f'Downloads/{fname}')
                zipdir(f'{i.src_folder_name}/', f'{i.dst_folder_name}/', zipf)
                zipf.write(f'Downloads/{fname}', arcname=f'{i.exe_name}.exe')
                print(zipf.getinfo(f'{i.exe_name}.exe').file_size)
                send_file(FTP_HOST, f'{i.arc_name}.zip', FTP_USER, FTP_PASS, FTP_PORT)
    else:
        print(f'Loading {fname} of {i.arc_name}...')
        urllib.request.urlretrieve(i.exe_link, f'Downloads/{fname}')
        with zipfile.ZipFile(f'out/{i.arc_name}.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipdir(f'{i.src_folder_name}/', f'{i.dst_folder_name}/', zipf)
            zipf.write(f'Downloads/{fname}', arcname=f'{i.exe_name}.exe')
        send_file(FTP_HOST, f'{i.arc_name}.zip', FTP_USER, FTP_PASS, FTP_PORT)
    try:
        os.remove(f'Downloads/{fname}')
    except:
        pass


if __name__ == '__main__':
    load_config('config.ini')
    items = load_list('init.csv')
    for i in items:
        compress(i)
