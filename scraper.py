import requests, shutil, time
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

options = webdriver.ChromeOptions()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--incognito')

driver = webdriver.Chrome(chrome_options=options)

try:
    driver.get("https://www.metatft.com/units")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'Unit_Img')))
    champions = driver.find_elements_by_class_name('Unit_Img')
    for x in range(len(champions)):
        e = champions[x]
        name = e.get_attribute('alt').lower()
        src = e.get_attribute('src')
        response = requests.get(src, stream=True)
        if response.ok:
            jpg_file = open('imgs/img_{name}.jpg'.format(name=name), 'wb')
            shutil.copyfileobj(response.raw, jpg_file)
            print("Saved image {name}".format(name=name))

    driver.get("https://www.metatft.com/traits")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'blademaster_plat')))
    traits = driver.find_elements_by_xpath('//img[@height="40"]')
    for x in range(len(traits)):
        e = traits[x]
        name = e.get_attribute('alt').replace(" ", "").lower()
        src = e.get_attribute('src')
        response = requests.get(src, stream=True)
        if response.ok:
            jpg_file = open('imgs/img_{name}.jpg'.format(name=name), 'wb')
            shutil.copyfileobj(response.raw, jpg_file)
            print("Saved image {name}".format(name=name))

    driver.get("https://www.metatft.com/items")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'Item_Img')))
    items = driver.find_elements_by_class_name('Item_Img')
    for x in range(len(items)):
        e = items[x]
        name = e.get_attribute('alt').replace(" ", "").replace("'", "").lower()
        src = e.get_attribute('src')
        response = requests.get(src, stream=True)
        if response.ok:
            jpg_file = open('imgs/img_{name}.jpg'.format(name=name), 'wb')
            shutil.copyfileobj(response.raw, jpg_file)
            print("Saved image {name}".format(name=name))
            
except:
    print("fkdlfj")

time.sleep(5)
driver.close()
driver.quit()

