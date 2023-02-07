import os
import sys
import zipfile
import urllib.request
from urllib.parse import urlparse
import csv
import ftplib
import configparser
import logging

logging.basicConfig(level=logging.INFO, filename="automation.log",filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

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
    try:
        config.read(cfg_file)  # читаем конфиг
        FTP_HOST = config["FTP"]["host"]
        FTP_PORT = int(config["FTP"]["port"])
        FTP_PATH = config["FTP"]["path"]
        FTP_USER = config["FTP"]["user"]
        FTP_PASS = config["FTP"]["pass"]
        logging.debug(f'Прочитан файл конфигурации {cfg_file}, FTP Хост: {FTP_HOST}, Пользователь: {FTP_USER}')
    except:
        logging.error(f'#Что-то не так с файлом конфигурации {cfg_file}')
        print(f'#Что-то не так с файлом конфигурации {cfg_file}')


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
    logging.debug(f'Загружено {str(len(items))} заданий на перепаковку...')
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
        flag = False
        if FTP_PATH != '':
            flag = True
            ftp.cwd(FTP_PATH)
        ftp_upload(ftp, fname)
        s = f'Файл {fname} успешно отправлен на FTP {FTP_HOST}'
        if flag:
            s = s + ' в директорию '+FTP_PATH
        logging.info(s)
        ftp.quit()
    except:
        logging.error(f'#Не могу отправить {fname} на FTP {FTP_HOST}')
        try:
            os.remove(fname)
        except:
            logging.error(f'Не могу удалить файл {fname}')
    os.chdir('..')


def compress(i: Item):
    remote_size = get_filesize_by_url(i.exe_link)
    logging.debug(f'------= Обрабатывается {i.arc_name} =------')
    fname = urlparse(i.exe_link).path.split('/')[-1]
    sub_folders = [name for name in os.listdir() if os.path.isdir(os.path.join(os.getcwd(), name))]
    if 'Downloads' not in sub_folders:
        os.mkdir('Downloads')
        logging.debug('Создана служебная папка Downloads')
    if 'out' not in sub_folders:
        os.mkdir('out')
        logging.debug('Создана служебная папка out')
    if find(f'{i.arc_name}.zip', 'out'):
        with zipfile.ZipFile(f'out/{i.arc_name}.zip', 'a', zipfile.ZIP_DEFLATED) as zipf:
            ef = False
            try:
                l_zip_size = zipf.getinfo(f'{i.exe_name}.exe').file_size
                if remote_size != l_zip_size:
                    ef = True
                    logging.info(f'Обнаружен разный размер файлов - Remote: {str(remote_size)}, Local: {str(l_zip_size)}')
            except:
                logging.error(f'Неизвестная проблема при обработке файла {i.arc_name}.zip')
                ef = True
            if ef:
                logging.info(f'Скачивается {fname} для архива {i.arc_name}.zip...')
                try:
                    urllib.request.urlretrieve(i.exe_link, f'Downloads/{fname}')
                    logging.info(f'Добавляется папка {i.dst_folder_name} в архив {i.arc_name}.zip')
                    zipdir(f'{i.src_folder_name}/', f'{i.dst_folder_name}/', zipf)
                    logging.info(f'Добавляется скачанный файл {fname} под именем {i.exe_name}.exe')
                    zipf.write(f'Downloads/{fname}', arcname=f'{i.exe_name}.exe')
                    send_file(FTP_HOST, f'{i.arc_name}.zip', FTP_USER, FTP_PASS, FTP_PORT)
                except:
                    logging.error(f'Не удалось скачать файл {fname}, проверьте доступность файла по ссылке {i.exe_link}')
    else:
        logging.info(f'Скачивается {fname} для архива {i.arc_name}.zip...')
        try:
            urllib.request.urlretrieve(i.exe_link, f'Downloads/{fname}')
            logging.info(f'Добавляется папка {i.dst_folder_name} в архив {i.arc_name}.zip')
            with zipfile.ZipFile(f'out/{i.arc_name}.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipdir(f'{i.src_folder_name}/', f'{i.dst_folder_name}/', zipf)
                logging.info(f'Добавляется скачанный файл {fname} под именем {i.exe_name}.exe')
                zipf.write(f'Downloads/{fname}', arcname=f'{i.exe_name}.exe')
            send_file(FTP_HOST, f'{i.arc_name}.zip', FTP_USER, FTP_PASS, FTP_PORT)
        except:
            logging.error(f'Не удалось скачать файл {fname}, проверьте доступность файла по ссылке {i.exe_link}')
    try:
        os.remove(f'Downloads/{fname}')
    except:
        pass


if __name__ == '__main__':
    load_config('config.ini')
    items = load_list('init.csv')
    for i in items:
        compress(i)
    try:
        os.rmdir('Downloads')
    except:
        pass
