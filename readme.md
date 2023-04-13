# Inventory Server

This is a simple inventory server to track products for small hobby businesses. The dataset it maintains is:
- Product Name: a descritive title (ie. "Umbrella Corp Vinyl Sticker")
- SKU: screaming snake case SKU (ie. UMBC_VINYL)
- Sold: track the amount sold
- Stock: track the amount currently in inventory
- Created: date in which the product was added to the database
- Retired: boolean flag for preserving data while excluding them from weekly reports

## Notable service features

- Maintain quantities of "In Stock" and "Sold" for various products.
- Add new products and document their release or drop date.
- Retire products from weekly emailed reports while maintaining otherwise normal behavior.
- Update versions can be hotswapped in for headless server convience.

## Implementation

Deviation from this is possible, but might require modifing the code. Future versions might implement feature
choices or other means to modify functionality without having to make changes to the source code. For now,
this software is an open source version of my own use case.

### Setup
Personally, I run this on a raspberrypi, headless, and with a barcode scanner. You can certainly get away
with running this on a main computer or something likewise. There is a feature here that only benefits from
running 24/7 though. That being the weekly log report. Database changes take immediate effect on the save file
though so it isn't a mandatory feature.

Before running any code, the first thing to do is modify the file the file ```edit_first_env.txt```. Inside
are already the fields that need to be filled out.
- These are the fields listed

Once these are filled out, save and exit. Rename that file to ```.env``` (no filename, just env extention
type). This is to allow the source code to read the sensitive data that should not be saved into git or
github.

The next thing is ```Products.json```. This is the "database" file. There is an example product preloaded
to give you an immediate hands on approach to initializing your database if that is easier. Delete this
exact entry though as json has no comment-out-code option.

### Running for the first time
The ```main.py``` file is the code that will run the main loop of the function. This method is to allow for
hot swapping updates. New versions of ```ProductScanner.py``` can be renamed as ```update.ver``` in the same
directory.

Once the program opens, there will be no preloaded products so you will have to enter them with the sequence
```Q+[SKU](Title)#```. Let's look at a couple examples.

    Q+[UMBC_VINYL](Umbrella Corp Vinyl Sticker)0
    Q+[MAOWS](Mouse Cat Toy)5
    Q+[SKOOMA_BRN](Do You Want Some Skooma Patch - Brown)2

Each line should be entered one by one, multi-add is not a current feature. This though will create 3 different
products in the json file used as the database. It will then initialize the Umbrella Corp sticker with 0 stock.
The cat toy will have 5 immediately in stock, and 2 of the patches. All of these then also get date tagged with
today's date. Date's don't have any direct use in this software, but can be useful to have for other business
reasons elsewhere.

### Stocking and Selling
The main interaction with the software is to either stock or sell products. This is handled by a simple text
command ```SKU*#```. Let's look at a couple examples.

    UMBC_VINYL*2
    MAOWS*-1
    SKOOMA_BRN*0

Again, each line should be entered one by one, multiline commands are not a current feature. The first example
is a positive numbered SKU, so we are increasing the stocked quantity. This will add 2 to Stock on that SKU.
There is no change to Sell. Next, we have -1 to sell 1 MAOWS. Stock will drop to 4 and Sell up to 1. For
SKOOMA_BRN, I have added a feature that I personally use in the event of gifting. 0 specifically will reduce
the Stock amount by 1, but wont increase Sell like a negative number would. This has a caviat of misrepresenting
the true manufactured quantities, but does support tracking populatiry by sales. Meaning, if I make 20 of
something that never sells, and I give them all away, it looks as though I never made them. Not great, but I am
more concerned with not making it look like I successfully sold all 20 when truely no one intentionall bought
them.

### Retire, Restore, and Inspect
These are helper functions to give you the information you need when you need it. Let's look at a couple examples.

    retire:UMBC_VINYL
    restore:MAOWS
    inspect:SKOOMA_BRN

Still, each line should be entered one by one, no multiline here yet. The first example will change the Umbrella
Corp sticker to retired. That means it won't show up on weekly report tables. You can still sell or stock it.
Next is restore. Rather than have the feature be ```retire:SKU``` to toggle retired on and off, retire and
restore respectively set the retire flag to ```true``` or ```false```. Lastly is inspect. When you stock or sell
things, by default, it will echo out sold and stock counts. Inspect is a way to easily poll that information
without making such an action.

### Menu features
- Force Email: Prematurely sends current contents of actions to email.
- Force Update: Prematurely runs update checker. CAUTION: This will drop floating data on action logs.
- Clear Screen: Just clears the screen of all the built up screen echos.
- Exit: Database modifications autosave, so exit will only drop weekly report data.

## Reading the Weekly Report Email

The weekly report email will be broken up into 4 sections.
- Datewise ins and outs
- Current inventory
- Stats
- Raw Log

### Section 1
Seperated by days, these tables come color coded as <span style="color:red">sold as red</span> and
<span style="color:green">stocked as green</span>. Dates are written on top, SKUs are to the left, and quantity
is to the right.

### Section 2
The current inventory gives 3 columns: SKU, Product Title, and Quantity. Default low stock is 2 or less and will
highlight that row in red.

### Section 3
These are the stats as of the email being sent. This notes manufactured and sold in both totals and for the week.
Also, current total of items in inventory.

### Section 4
This is more of a debugging section as this is the inputs with their timestamps. Errors here are supposed to be
highlighted in red for convience, but due to a current problem yet to be fixed, it doesn't change the color back.
The feature works, but not as intended.

## Tie-in

For best results in entering Sell/Stock codes, I have yet to release the companion app I personally made for
this. It is currently extremely hard-coded to specification and not currently suitable for sharing. However,
the concept, should you chose some likewise homemade solution, is to generate an image gallery of buttons
that callback their associated SKU. Then with some counter buttons, increment or decrement the quantity part.

## Compatability

Current version uses a method for threading input with the main loop that doesn't work on Windows. Works fine
with linux. Untested on Mac.
