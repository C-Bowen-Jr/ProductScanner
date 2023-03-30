import ProductScanner as PS
from importlib import reload
import os

def main():
  PS.ProdScanInit()
  LoopState = PS.ProdScanMain()
  while(LoopState != "Exit"):
    if LoopState == "Update":
      if os.path.exists("update.ver"):
        updateFile = open("update.ver","r")
        oldFile = open("ProductScanner.py", "w")
        oldFile.write(updateFile.read())
        oldFile.close()
        updateFile.close()
        os.remove("update.ver")
        print ("Updated Server; restarting module...")
        reload(PS)
      # /if os.path.exists
    # /loopstate  
    PS.ProdScanInit()
    LoopState = PS.ProdScanMain()
  # /while loopstate
# / main    

if __name__ == "__main__":
    main()
