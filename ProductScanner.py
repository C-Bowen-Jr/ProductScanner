# -*- coding: utf-8 -*-

# Inventory Server Product Scanner
# Created 2019
# GNU GPLv3

import os
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time, traceback, threading
import queue
from datetime import datetime
import select
import sys
import json

# Version breakdown: Major change. Minor fix/change. Times code modified
Version = "5.6.31"

# Global variables
RunState = "Run"
DebugMode = False
WeeklyReport = []
ProductArray = []
wkStock = 0
wkSell = 0
choice = -1
input_queue = queue.Queue()
load_dotenv()

# Classes
class Product:
  Title = "NULL"            # Name of Product
  SKU = "SKU"               # SKU of Product
  Stocked = 0               # Number in stock
  Sold = 0                  # Number sold
  Retired = False           # Retired don't show up on low stock
  Released = "MM/DD/YYYY"   # Released date

  # Init, takes ProductName and ..SKU to create a Product datapoint
  def __init__(self, ProductName, ProductSKU, ProductStocked, ProductSold):
    self.Title = ProductName
    self.SKU = ProductSKU
    self.Stocked = ProductStocked
    self.Sold = ProductSold

  def PrintProduct(self):
    print (f"{self.Title} [In Stock: {self.Stocked} Sold: {self.Sold}]")

  def GetManufactured(self):
    return self.Stocked + self.Sold

  def SetRetired(self, RetireState):
    self.Retired = RetireState

  def GetDictionaryForm(self):
    DictForm = {"name": self.Title, "sku": self.SKU, "stock": self.Stocked, "sold": self.Sold, "released": self.Released,"retired": self.Retired}
    return DictForm

  def SetReleasedToPyDate(self, PyDatetimeDate):
    self.Released = PyDatetimeDate.strftime('%m/%d/%Y')

# Functions
# Threading task delay    ------------------
def every(delay, task):
  next_time = time.time() + delay
  while True:
    time.sleep(max(0, next_time - time.time()))
    try:
      task()
    except Exception:
      traceback.print_exc()
      # in production code you might want to have this instead of course:
      # logger.exception("Problem while executing repetitive task.")
    # skip tasks if we are behind schedule:
    next_time += (time.time() - next_time) // delay * delay + delay

def get_input():
  while True:
    input_data = input().strip()
    input_queue.put(input_data)

# String Stripper, returns a subset of a string between 2 points
def stringStripper(original, begining, ending):
  if begining == None:
    begining = 0 # 0 is the first index to the string
  elif begining not in original:
    return "Error: Begining not found"
  else:
    begining = original.find(begining)+1
  if ending == None:
    ending = len(original) # len() is the last index to the string
  elif ending not in original:
    return "Error: Ending not found"
  else:
    ending = original.find(ending)

  return original[begining:ending]


# Parse parscode variables to get html code
def parsDecode(parscode):
  global WeeklyReport, ProductArray, wkStock, wkSell
  htmlreturn = ""
  counter = 0
  datebreak = 0
  wreDate = ""
  wreSKU = ""
  wreQty = 0

  if parscode == "LOGTABLE":
    for WREntry in WeeklyReport:
      if "&" in WREntry: # Expected code '&date[SKU]quantity'
        wreDate = stringStripper(WREntry, "&", "[")
        if datebreak != wreDate:
          if datebreak != 0: # subsequent days need an end to the prior day's table
            htmlreturn += "\n</table>"
          htmlreturn += """\n<table style="color:white;"><caption><b>{0}</b></caption>
    <tr>
      <th>Product</th>
      <th>Qty</th>
    </tr>""".format(wreDate)
          datebreak = wreDate # update a new datebreak point
        wreSKU = stringStripper(WREntry, "[","]")
        wreQty = int(stringStripper(WREntry, "]", None))
        if wreQty > 0: # positive is green
          wkStock += wreQty
          htmlreturn += '<tr style="background-color: green;">'
        elif wreQty < 0: # negative is red
          wkSell -= wreQty
          htmlreturn += '<tr style="background-color: red;">'
        else:
          htmlreturn += '<tr>'

        htmlreturn +="""
      <td>{0}</td>
      <td>{1}</td>
    </tr>""".format(wreSKU, wreQty)
    # After all WREntry entries are parsed, add a final table break
    htmlreturn += "\n</table>"

  elif parscode == "INVENTORYTABLE":
    htmlProdTemplate = """<tr{3}>
      <td>{0}</td>
      <td>{1}</td>
      <td>{2}</td>
    </tr>
"""
    for prod in ProductArray:
      if not prod.Retired and prod.Stocked > 1:
        htmlreturn += htmlProdTemplate.format(prod.SKU, prod.Title, prod.Stocked, '')
      elif not prod.Retired:
        htmlreturn += htmlProdTemplate.format(prod.SKU, prod.Title, prod.Stocked,' style="background-color: red;"')

  elif parscode == "TOTALSOLD":
    for prod in ProductArray:
      counter += prod.Sold
    htmlreturn = "<td>{0}</td>".format(counter)
  elif parscode == "TOTALMANUFACTURED":
    for prod in ProductArray:
      prod.GetManufactured()
      counter += prod.GetManufactured()
    htmlreturn = "<td>{0}</td>".format(counter)
  elif parscode == "WEEKLYSOLD":
    htmlreturn += "<td>{0}</td>".format(wkSell)
  elif parscode == "WEEKLYMANUFACTURED":
    htmlreturn += "<td>{0}</td>".format(wkStock)
  elif parscode == "CURRENTLYSTOCKED":
    for prod in ProductArray:
      counter += prod.Stocked
    htmlreturn = "<td>{0}</td>".format(counter)
  elif parscode == "FINALREPORT":
    for entry in WeeklyReport:
      if entry.find("ERROR") > -1: # Error print in bold red
        htmlreturn += '<b style="color:red;">{0}</b><br>'.format(entry)
      else:
        htmlreturn += "{0}<br>".format(entry)
  else:
    return "<b>ERROR in parscode</b>"
  return htmlreturn

# WEEKLY REPORT FUNCTIONS
def SendReportEmail():
  global RunState, WeeklyReport, ProductArray, DebugMode

  # Create message container - the correct MIME type is multipart/alternative.
  msg = MIMEMultipart('alternative')
  msg['Subject'] = "Weekly Stock Report"
  msg['To'] = os.getenv("EMAIL_TO")
  msg['From'] = os.getenv("EMAIL_FROM")
  MsgFromArray = ""
  Stocks = []
  EmailFormated = ""
  html = open("ServerEmail_Template.html", "r")

  server = smtplib.SMTP_SSL(os.getenv("SMTP_NAME"), int(os.getenv("SMTP_PORT")))
  server.login(os.getenv("EMAIL_FROM"), os.getenv("EFROM_PASSWORD"))


  # Build Weekly In/Out Report log
  MsgFromArray = '\n'.join(WeeklyReport)

  # Sort the list by SKU alphabeticaly and leave out retired products
  ProductArray.sort(key=lambda x: x.SKU, reverse=False)
  for Prods in ProductArray:
    if not Prods.Retired:
      Stocks.append(f"{Prods.Stocked}: {Prods.Title}")

  for htmlLine in html:
    # check if line contains parscode ie ##variable##
    if "##" in htmlLine: #htmlLine.find("##") != -1:
      stripParscode = htmlLine[htmlLine.find("##")+2:]
      stripParscode = stripParscode[:stripParscode.find("##")]
      EmailFormated += parsDecode(stripParscode)
    else:
      EmailFormated += htmlLine

  # Record the MIME types of both parts - text/plain and text/html.
  part1 = MIMEText("HTML code", 'plain')
  part2 = MIMEText(EmailFormated, 'html')

  # Attach parts into message container.
  # According to RFC 2046, the last part of a multipart message, in this case
  # the HTML message, is best and preferred.
  msg.attach(part1)
  msg.attach(part2)

  if DebugMode:
    #save email as html file instead
    with open("EmailReport.html", "w") as f:
      f.write(EmailFormated)
  else:
    #actually send email
    server.sendmail(
      os.getenv("EMAIL_FROM"),
      os.getenv("EMAIL_TO"),
      msg.as_string())
    print (f"({datetime.now()}) Email sent to mail server")
  html.close()
  server.quit()

def PerformUpdateCheck():
  global RunState, WeeklyReport

  # Check if "update.ver" exists, this is ProductScanner.py renamed temporarily and will replace the old version
  if os.path.exists("update.ver"): # Update is available
    updateVersionString = open("update.ver","r")
    line = updateVersionString.readline().replace("\n","")
    while "Version = " not in line:   # if Version code isn't here, check next line
      line = updateVersionString.readline().replace("\n","")
    RunState = "Update" # Upon completion of PS.py' main loop, main.py's main loop will get update OK
    choice = "Update" # feed user input with update command because we cant kill input() loop

    WeeklyReport.append(f"Update from {Version} to {line} - [{dtNow}]")
    updateVersionString.close()

def SundayNineAM():
  global RunState, WeeklyReport, wkStock, wkSell, choice
  dtNow = datetime.now()
  if dtNow.hour == 9:#is 9 am
    if dtNow.weekday() == 6: # is Sunday
      # len() > 0 is something to report, (find."Update" AND len() > 1)
      if WeeklyReport:       #the more pythonic way of len(WR) > 0
        # send report and reset weekly detailings
        SendReportEmail()
        WeeklyReport = []
        wkStock = 0
        wkSell = 0

      PerformUpdateCheck()

def env_setup():
  return os.path.isfile(".env")

# --------- Raw SAVE DATA LINES
def ReadSaveData():
  jFile = open("Products.json", "r")
  ProductsJsonArray = json.load(jFile)
  jFile.close()

  return JsonToArray(ProductsJsonArray)

def WriteSaveData(ProductsObjectArray):
  global DebugMode
  if DebugMode:  #dont save changes made durring debugmode
    return

  jFile = open("Products.json", "w")

  jFile.seek(0)
  jFile.write(json.dumps(ProductsObjectArray, indent = 2))
  jFile.truncate()
  jFile.close()

# /////////////////////////////////
# --------- Program specific save data parser
def JsonToArray(ProductsJsonArray):
  # Take the json array and create an array of ProdObjects
  tempProductObjectsArray = []
  for jsonProd in ProductsJsonArray:
    initProduct = Product(jsonProd["name"],jsonProd["sku"],jsonProd["stock"],jsonProd["sold"])
    initProduct.SetRetired(jsonProd["retired"])
    initProduct.Released = jsonProd["released"]
    tempProductObjectsArray.append(initProduct)

  return tempProductObjectsArray

def ArrayToJson(ProductObjectArray):
  # Take the array of ProdObjects and create a json array
  tempProductsJsonArray = []
  for prodObject in ProductObjectArray:
    tempProductsJsonArray.append(prodObject.GetDictionaryForm())

  return tempProductsJsonArray

# ////////////////////////////////

def ProdScanInit():
  global RunState, DetailsMode, WeeklyReport, ProductArray, inputChoice
  ProductArray = []

  ProductArray = ReadSaveData()

  ThreadTask = threading.Thread(target=lambda: every(60, SundayNineAM))
  ThreadTask.daemon = True
  ThreadTask.start()
  input_thread = threading.Thread(target=get_input)
  input_thread.daemon = True
  input_thread.start()

# Main Function
def ProdScanMain():
  global RunState, WeeklyReport, ProductArray, inputChoice
  MenuOptions = ["Force Email","Force Update", "Clear Screen","Exit"]
  WREcho = ""
  WRETS = datetime.now()

  inputChoice = ""
  Opt = 1

  print (f"---Inventory Server Product Scanner---  v({Version})")
  if DebugMode:
    print ("WARNING!! DEBUG MODE ACTIVE, NO SAVES WILL BE MADE!")
  print ("Scan 'Q+[SKU](Product Name)#' to add a new product.")
  print ("Scan '[SKU]*#' with +/- numbers to stock/sell, or use '0' for freebies")
  for Option in MenuOptions:
    print (str(Opt) + ": " + Option)
    Opt += 1

  #Test bed on main input loop
  while True:
    if not input_queue.empty():
      inputChoice = input_queue.get()
    else:
      inputChoice = ""

    if str(inputChoice).isdigit():
      # offset inputChoice for a 0 based index of menu choices
      inputChoice = int(inputChoice) - 1

      # Menu option choices
      # Force email with stock details (wont erase weekly report)
      if MenuOptions[inputChoice] == "Force Email":
        if env_setup():
          SendReportEmail()
        else:
          print("Please setup your .env file")

      elif MenuOptions[inputChoice] == "Clear Screen":
        pass #print ("The screen is about to be cleared")
      elif MenuOptions[inputChoice] == "Force Update":
        print ("Checking...")
        PerformUpdateCheck()
      elif MenuOptions[inputChoice] == "Exit":
        print ("Saving...")
        WriteSaveData(ArrayToJson(ProductArray))
        RunState = "Exit"

      # Save and Exit
      WriteSaveData(ArrayToJson(ProductArray))
      return RunState
    else:
      #QR action code scanned
      WeeklyReport.append(inputChoice) # Weekly Report, only add if not a menu item
      WRETS = datetime.now()
      FoundProd = False
      # QuickAdd code found, parse
      if "Q+[" in inputChoice:
        tempSKU = stringStripper(inputChoice, "[","]")
        tempTitle = stringStripper(inputChoice, "(",")")
        tempMade = stringStripper(inputChoice, ")", None)
        FoundProd = True #set if creating, technically true so no error later
        WREcho = f"Creating new product! {tempTitle}[{tempSKU}] with an initial batch of {tempMade}"
        print (WREcho)
        WREcho = f"{WRETS.date()} {WRETS.hour}:{WRETS.minute} | {WREcho}"
        WeeklyReport.append(WREcho) # Weekly Report
        NewProduct = Product(tempTitle, tempSKU,int(tempMade),0)
        NewProduct.SetReleasedToPyDate(WRETS.date())
        ProductArray.append(NewProduct)
        WriteSaveData(ArrayToJson(ProductArray))

      # Check each product against the scanned barcode
      if "retire" in inputChoice or "restore" in inputChoice or "inspect" in inputChoice:
        for Prods in ProductArray:
          # Check for the retire/rework code
          if "retire:" in inputChoice and Prods.SKU == stringStripper(inputChoice, ":", None) :
            # Get out of the loop now that we found the right one
            FoundProd = True
            Prods.SetRetired(True)
            WeeklyReport.append(f"{Prods.Title} has been retired.")
            break
          elif "restore:" in inputChoice and Prods.SKU == stringStripper(inputChoice, ":", None) :
            # Get out of the loop now that we found the right one
            FoundProd = True
            Prods.SetRetired(False)
            WeeklyReport.append(f"{Prods.Title} has been taken out of retirement.")
            break
          elif "inspect:" in inputChoice and Prods.SKU == stringStripper(inputChoice, ":", None) :
            # Get out of the loop now that we found the right one
            FoundProd = True
            print (f"Inspecting > {Prods.SKU}")
            Prods.PrintProduct()
            break

      for Prods in ProductArray:
        # Business as normal
        SKUcount = 9999
        try:
          SKUcount = int(stringStripper(inputChoice, "*", None))#choice[choice.find("*")+1:])
        except:
          WREcho = f"'{inputChoice}' was scanned, but multiplier was not found"
          FoundProd = False
          break

        # is this sku the choice sku and is it less than 0 (selling)
        if Prods.SKU == stringStripper(inputChoice, None, "*") and SKUcount < 0:
          Prods.Stocked += SKUcount # adding negative number subtracts stock
          Prods.Sold -= SKUcount # subtracting negative number increases sold
          Prods.PrintProduct()
          FoundProd = True
          WREcho = f"&{WRETS.date()}[{Prods.SKU}]{SKUcount}"
          WeeklyReport.append(WREcho) # Weekly Report
          WriteSaveData(ArrayToJson(ProductArray))
          break

        # is this sku the choice sku and is it more than 0 (restocking)
        elif Prods.SKU == stringStripper(inputChoice, None, "*") and SKUcount > 0 and SKUcount < 100:
          Prods.Stocked += SKUcount
          Prods.PrintProduct()
          FoundProd = True
          WREcho = f"&{WRETS.date()}[{Prods.SKU}]{SKUcount}"
          WeeklyReport.append(WREcho) # Weekly Report
          WriteSaveData(ArrayToJson(ProductArray))
          break

        elif Prods.SKU == stringStripper(inputChoice, None, "*") and SKUcount == 0:
          Prods.Stocked -= 1
          Prods.PrintProduct()
          FoundProd = True
          WREcho = f"&{WRETS.date()}[{Prods.SKU}]{SKUcount}"
          WeeklyReport.append(WREcho) # Weekly Report
          WriteSaveData(ArrayToJson(ProductArray))
          break

      # No matching product, but also ignore the open/close statements
      if not FoundProd:
        WREcho = f" -{WRETS.date()} {WRETS.hour}:{WRETS.minute} | ERROR '{inputChoice}''"
        WeeklyReport.append(WREcho) # Weekly Report


# Notes:
#

