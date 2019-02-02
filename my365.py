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
    # ログインに必要な情報を設定する。
    # Cookieに日本語指定がない場合、利用者言語が英語となるため後続の文字列抽出ができなくなる。
    cookies = dict(language='ja')
    payload = {"user": accountId, "password": password}

    # ログイン処理を行い、セッションIDを取得する。
    # リダイレクトを無効にしておかないと転送先の情報を取得してしまう。
    response = requests.post(
        host + '/login', data=payload, allow_redirects=False, cookies=cookies)

    # ログイン当初のページのステータスは302となるので確認
    if response.status_code != 302:
        e = Exception("[Error] HTTP status: {}".format(response.status_code))
        raise e

    # CookieにセッションID('SESSID')が含まれているかをチェック
    if response.cookies.get('SESSID') is None:
        e = Exception("[Error] Response does not contain SESSID")
        raise e

    return response.cookies.get('SESSID')


def get_day_pages(month):
    """
    マイカレンダーページから個別ページのURLを収集する
        :param month: 探索対象となる月(例：'201902')
    """
    # マイカレンダー(月間ページ)取得に必要な情報を設定する。
    cookies = dict(SESSID=my365sid, language='ja')

    # my365へアクセス
    r = requests.get('{}/{}/{}'.format(my365host, my365user, month),
                     cookies=cookies)

    # 投稿がある日へ繋がるURLを抽出する
    return re.findall('/' + my365user + '/p/[0-9]{8}', r.text)


def get_image_info(year, day):
    """
    探索対象日に投稿された画像の格納URLを取得する
        :param year: 探索対象年
        :param day: 探索対象日ページのパス
    """
    # 個別ページ取得に必要な情報を設定する。
    cookies = dict(SESSID=my365sid, language='ja')

    # my365へアクセス
    r = requests.get(my365host + day, cookies=cookies)

    # 個別ページに含まれる投稿画像のURLを取得する
    htmlString = r.text
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
    # 画像格納先から画像データを取得する(my365ではAmazonのAWS S3)
    response = requests.get(path, allow_redirects=False, timeout=timeout)

    # 正常に取得できたかをステータスコードで確認する
    if response.status_code != 200:
        e = Exception("[Error] HTTP status: {}".format(response.status_code))
        raise e

    # 取得できたデータのタイプが画像かを確認する
    content_type = response.headers["content-type"]
    if 'image' not in content_type:
        e = Exception("[Error] Content-Type: {}".format(content_type))
        raise e

    # 取得したデータを返却する
    return response.content


def save_image(path, image):
    """
    docstring here
        :param path: 画像の保存先
        :param image: 画像データ
    """
    # 保存先を開き、画像データを書き込む
    with open(path, "wb") as fout:
        fout.write(image)


if __name__ == "__main__":
    # コンフィグファイルを読み込む
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, 'UTF-8')

    # 全体で使う変数を用意する
    global my365host
    global my365user
    global my365sid

    # 主要な設定値を設定する
    my365host = config.get('settings', 'host')
    my365user = config.get('user', 'account')
    my365password = config.get('user', 'password')
    my365savedir = config.get('io', 'outputDirectory')
    my365image_list_file = './' + config.get('io', 'imagelist')

    # 画像の保存先があるかを確認し、なければ作成する
    if not os.path.exists(my365savedir):
        os.mkdir(my365savedir)

    # セッションIDを取得する
    print("my365にログインし、セッションIDを取得します。")
    my365sid = get_session_id(my365host, my365user, my365password)
    print("  --> セッションIDを取得しました。（{}）".format(my365sid))

    # 当月と遡る一番古い月を設定する。
    focus = datetime.datetime.now()
    limit = datetime.datetime(
        int(config.get('settings', 'firstYear')),
        int(config.get('settings', 'firstMonth')),
        1, 0, 0)

    # 投稿された画像一覧を格納するためのデータフレーム
    ipdf = pd.DataFrame(columns=['date', 'imagepath'])

    # 画像URLの取得開始
    print("my365に投稿された画像のURL一覧を生成します。")
    while focus >= limit:
        # 処理対象となる年と月
        year = focus.year
        month = focus.month

        # 処理状況の表示
        print(
            "\r  --> {:04d}年{:02d}月の情報を収集しています".format(year, month), end="")

        # 投稿がある日に繋がるURL一覧を取得
        day_pages = get_day_pages('{:04d}{:02d}'.format(year, month))

        # 個別ページごとに投稿画像のURLを取得して一覧に格納する
        for day in day_pages:
            ips = pd.Series(get_image_info(year, day), index=ipdf.columns)
            ipdf = ipdf.append(ips, ignore_index=True)

        # １ヶ月前に遡る
        focus = focus + relativedelta(months=-1)

    # 解析できた画像の枚数
    total = len(ipdf)

    # 処理状況の表示
    print("\r  --> 完了しました。解析できた画像は {} 枚です。".format(total))

    # 投稿された画像のURL一覧をCSVファイルに格納する
    ipdf.to_csv(my365image_list_file, index=False)

    # 処理状況の表示
    print("  --> 画像のURL一覧をファイルへ出力しました。")
    print("my365に投稿された画像のダウンロードを開始します。")

    # ループ分のためにリスト化
    date_list = ipdf.date.tolist()
    path_list = ipdf.imagepath.tolist()

    # 画像を１枚ずつダウンロードする
    counter = 0
    for date, path in zip(date_list, path_list):
        # 画像格納先から画像データを取得する
        image = get_image_from_s3(path)
        # ファイル名を決定する
        save_name = date + '_' + os.path.basename(path)
        # ファイルを保存する
        save_image('./{}/{}'.format(my365savedir, save_name), image)
        # 処理状況の表示
        counter = counter + 1
        if(counter % 10 == 0):
            print("\r  --> {}枚中{}枚が完了".format(total, counter), end="")

    # 処理状況の表示
    print("\r  --> ダウンロードが完了しました。")
