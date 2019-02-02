# -*- coding: utf-8 -*-
import os.path
import configparser
import requests
import re
import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

# コンフィグファイル
CONFIG_FILE = './config.ini'


def get_session_id(host, accountId, password):
    """
    ログイン済みのセッションIDを取得する
        :param host: アクセス対象URL
        :param accountId: アカウントID
        :param password: パスワード
    """
    cookies = dict(language='ja')
    payload = {"user": accountId, "password": password}
    response = requests.post(
        host + '/login', data=payload, allow_redirects=False, cookies=cookies)

    if response.status_code != 302:
        e = Exception("[Error] HTTP status: {}".format(response.status_code))
        raise e

    if response.cookies.get('SESSID') is None:
        e = Exception("[Error] Response does not contain SESSID")
        raise e

    return response.cookies.get('SESSID')


def get_day_pages(month):
    """
    マイカレンダーページから個別ページのURLを収集する
        :param month: 探索対象となる月(例：'201902')
    """
    # ACCESS MY365 by Using SESSION_ID
    cookies = dict(SESSID=my365sid, language='ja')
    r = requests.get('{}/{}/{}'.format(my365host, my365user, month),
                     cookies=cookies)
    # Return URL List
    return re.findall('/' + my365user + '/p/[0-9]{8}', r.text)


def get_image_info(year, day):
    """
    探索対象日に投稿された画像の格納URLを取得する
        :param year: 探索対象年
        :param day: 探索対象日ページのパス
    """
    # ACCESS MY365 by Using SESSION_ID
    cookies = dict(SESSID=my365sid, language='ja')
    r = requests.get(my365host + day, cookies=cookies)

    # HTML String
    htmlString = r.text
    # Return URL List
    return [str(year) + '年' + re.findall('[0-9]{2}月[0-9]{2}日', htmlString)[0],
            re.findall(
                'http://my365.s3.amazonaws.com/store/[0-9]{8}/600x600/50/\w+.jpg', htmlString)[0]
            ]


def get_image_from_s3(path, timeout=10):
    """
    画像が格納されているストレージからデータを取得する
        :param path: 画像のURL
        :param timeout=10: タイムアウト
    """
    response = requests.get(path, allow_redirects=False, timeout=timeout)

    if response.status_code != 200:
        e = Exception("[Error] HTTP status: {}".format(response.status_code))
        raise e

    content_type = response.headers["content-type"]
    if 'image' not in content_type:
        e = Exception("[Error] Content-Type: {}".format(content_type))
        raise e

    return response.content


def save_image(path, image):
    with open(path, "wb") as fout:
        fout.write(image)


if __name__ == "__main__":
    # Read Config File
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, 'UTF-8')

    # Create Global Variables
    global my365host
    global my365user
    global my365sid

    # Config Parameter
    my365host = config.get('settings', 'host')
    my365user = config.get('user', 'account')
    my365password = config.get('user', 'password')
    my365savedir = config.get('io', 'outputDirectory')
    my365image_list_file = './' + config.get('io', 'imagelist')

    # Check and Create Image Directory
    if not os.path.exists(my365savedir):
        os.mkdir(my365savedir)

    # Get Session ID
    print("my365にログインし、セッションIDを取得します。")
    #my365sid = '2253ndgkag3otcdv1j7aboovh2'
    my365sid = get_session_id(my365host, my365user, my365password)
    print("  --> セッションIDを取得しました。（{}）".format(my365sid))

    # Make Current Date and First Date
    focus = datetime.datetime.now()
    limit = datetime.datetime(
        int(config.get('settings', 'firstYear')),
        int(config.get('settings', 'firstMonth')),
        1, 0, 0)

    # AWS Image Path List (DataFrame)
    ipdf = pd.DataFrame(columns=['date', 'imagepath'])

    # Print Status
    print("my365に投稿された画像のURL一覧を生成します。")

    # Create Daily Page List
    while focus >= limit:
        # Focus Year & Month
        year = focus.year
        month = focus.month

        # Print Status
        print(
            "\r  --> {:04d}年{:02d}月の情報を収集しています".format(year, month), end="")

        # Get Daily Page List
        day_pages = get_day_pages('{:04d}{:02d}'.format(year, month))

        # Collect Daily Image Paths
        for day in day_pages:
            ips = pd.Series(get_image_info(year, day), index=ipdf.columns)
            ipdf = ipdf.append(ips, ignore_index=True)

        # Calculate 1 month ago
        focus = focus + relativedelta(months=-1)

    # Total Image Counter
    total = len(ipdf)

    # Print Status
    print("\r  --> 完了しました。解析できた画像は {} 枚です。".format(total))

    # Outpu Image URL List
    ipdf.to_csv(my365image_list_file, index=False)

    # Print Status
    print("  --> 画像のURL一覧をファイルへ出力しました。")
    print("my365に投稿された画像のダウンロードを開始します。")

    date_list = ipdf.date.tolist()
    path_list = ipdf.imagepath.tolist()

    counter = 0
    for date, path in zip(date_list, path_list):
        # Download Images from AWS S3
        image = get_image_from_s3(path)
        # Set File Name
        save_name = date + '_' + os.path.basename(path)
        # File Save
        save_image('./{}/{}'.format(my365savedir, save_name), image)
        # Print Status
        counter = counter + 1
        if(counter % 10 == 0):
            print("\r  --> {}枚中{}枚が完了".format(total, counter), end="")

    # Print Status
    print("\r  --> ダウンロードが完了しました。")
