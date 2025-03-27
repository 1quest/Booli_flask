from flask import Flask, render_template, redirect, url_for, flash
import requests
from bs4 import BeautifulSoup
import re
from flask_sqlalchemy import SQLAlchemy

url_booli_uppsala_kommun = 'https://www.booli.se/sok/till-salu?areaIds=1116&objectType=Villa&maxListPrice=7000000&minRooms=3.5'
url_booli_home = 'https://www.booli.se'

app = Flask(__name__)
app.secret_key = '1116&objectType=Villa'  # Necessary for flashing messages, should be long and random

# Initialize database connection
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username="GoHome2",
    password="uZDzj4hxuGxBZZw",
    hostname="GoHome2.mysql.pythonanywhere-services.com",
    databasename="GoHome2$Booli",
)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Helper function to safely extract text
def safe_extract(li_elements, index, suffix=''):
    try:
        return li_elements[index].find('p').get_text(strip=True).replace(suffix, '').replace(u'\xa0', u'').replace('rum', '').strip()
    except IndexError:
        return None

class RealEstateListing(db.Model):
    __tablename__ = 'real_estate_listings'

    id = db.Column(db.Integer, primary_key=True)
    booli_price = db.Column(db.Float, nullable=False)
    boarea = db.Column(db.Float, nullable=False)
    rum = db.Column(db.Integer, nullable=False)
    biarea = db.Column(db.Float, nullable=True)
    tomtstorlek = db.Column(db.Float, nullable=True)
    byggar = db.Column(db.Integer, nullable=True)
    utgangspris = db.Column(db.Float, nullable=True)
    bostadstyp = db.Column(db.String(50), nullable=False)
    omrade = db.Column(db.String(100), nullable=False)
    stad = db.Column(db.String(100), nullable=False)
    price_text = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)

    def __init__(self, booli_price, boarea, rum, biarea, tomtstorlek, byggar, utgangspris, bostadstyp, omrade, stad, price_text, url):
        self.booli_price = booli_price
        self.boarea = boarea
        self.rum = rum
        self.biarea = biarea
        self.tomtstorlek = tomtstorlek
        self.byggar = byggar
        self.utgangspris = utgangspris
        self.bostadstyp = bostadstyp
        self.omrade = omrade
        self.stad = stad
        self.price_text = price_text
        self.url = url

    def __repr__(self):
        return (f"RealEstateListing(booli_price={self.booli_price}, boarea={self.boarea}, rum={self.rum}, "
                f"biarea={self.biarea}, tomtstorlek={self.tomtstorlek}, byggar={self.byggar}, "
                f"utgangspris={self.utgangspris}, bostadstyp={self.bostadstyp}, omrade={self.omrade}, "
                f"stad={self.stad}, price_text={self.price_text}, url={self.url})")

    def storeInDB(self):
        db.session.add(self)
        db.session.commit()

class DatabaseInitializer:
    def __init__(self, app):
        self.app = app
        self.db = db

    def initialize(self):
        with self.app.app_context():
            self.db.create_all()

def booli_find_number_of_pages_data(url):
    request = requests.get(url)
    soup = BeautifulSoup(request.text, 'lxml')
    data = soup.find_all('p', class_='m-2')
    # Regular expression to match the last number inside <!-- -->
    pattern = r'<!-- -->(\d+)<\/p>]'

    # Find all matches
    matches = re.findall(pattern, str(data))

    if matches:
        # Extract the last match and get the number
        last_number = matches[-1]
    else:
        print("No matches found")
        last_number = 0
    return int(last_number)

def booli_scrape_links(url, pages):
    hrefs = []
    for i in range(1, pages + 1):
        url_loop = f"{url}&page={i}"
        try:
            # Send a GET request to the URL
            response = requests.get(url_loop)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)

            # Parse the response content with BeautifulSoup
            soup = BeautifulSoup(response.text, 'lxml')

            # Select all links with the specific class and href containing '/annons/'
            links = soup.select("a.expanded-link.no-underline.hover\\:underline[href*='/']")

            # Extract the href values from the link elements and append to the list
            hrefs.extend([link['href'] for link in links])

        except requests.RequestException as e:
            print(f"An error occurred on page {i}: {e}")
            continue  # Continue to the next page even if there's an error on the current page

    return hrefs

def booli_scrape_objects(links):
    listings = []
    for j, row in enumerate(links):
        # Compile the listing-url
        url_loop = url_booli_home + links[j]
        # Send a GET request to the URL
        response = requests.get(url_loop)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        soup = BeautifulSoup(response.text, 'lxml')
        print("URL: " + url_loop)

        # Find the span element with class 'heading-2'
        price_span = soup.find('span', class_='heading-2')

        if price_span:
            # Extract the text content and remove the 'kr' part
            price_text = price_span.get_text(strip=True).replace(u'\xa0', u'').replace('kr', '')
        try:
            int(price_text)
        except:
            price_text = '-999999'

        # Find the p element with the specific class containing the desired price
        booli_price = soup.find('p', class_='heading-5 whitespace-nowrap first-letter:uppercase tabular-nums lining-nums')

        if booli_price:
            # Extract the text content and remove the ' kr' part
            booli_price = booli_price.get_text(strip=True).split(' ')[0].replace(u'\xa0', u'').replace('kr', '')
        else:
            booli_price = '-999999'

        # Find the ul element with the housing details
        details_soup = soup.find('ul', class_='flex flex-wrap gap-y-4 gap-x-8 sm:gap-x-12 flex flex-wrap mt-6')

        # Find all <li> elements within the <ul>
        li_elements = details_soup.select('ul.flex > li')

        # Extract the desired values safely
        boarea = safe_extract(li_elements, 0, 'm²')
        rum = safe_extract(li_elements, 1)
        biarea = safe_extract(li_elements, 2, 'm²')
        tomtstorlek = safe_extract(li_elements, 3, 'm²')
        byggar = safe_extract(li_elements, 4)

        # Find the p element with the specific class containing the desired price
        utgangspris = soup.find('span', class_='text-sm text-content-secondary mt-2')

        # Regex pattern to extract text between > and <, excluding the brackets
        pattern = r'>([^<]+)<'

        # Find all matches
        bostadstyp, omrade, stad = re.findall(pattern, str(utgangspris))[0].split(' · ')

        listing = RealEstateListing(booli_price, boarea, rum, biarea, tomtstorlek, byggar, price_text, bostadstyp, omrade, stad, price_text, url_loop)
        listings.append(listing)

    return listings

# Define the ETL_db method
def etl_db():
     # ETL logic
     print("ETL process started")
     try:
         pages = booli_find_number_of_pages_data(url_booli_uppsala_kommun)
         links = booli_scrape_links(url_booli_uppsala_kommun, pages)
         listings = booli_scrape_objects(links[0])
         #for listing in listings:
         #listings[0].store_in_db()
     except Exception as e:
        flash(f"An error occurred while initializing the database: {str(e)}", "danger")
     print("ETL process finished")
     return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run_etl')
def run_etl():
    etl_db()
    return redirect(url_for('index'))

# Define the Connect_db method
@app.route('/connect_db')
def connect_db_route():
    try:
        # Initialize the database
        print("Initializing db connection")
        db_initializer = DatabaseInitializer(app)
        db_initializer.initialize()
    except Exception as e:
        flash(f"An error occurred while initializing the database: {str(e)}", "danger")
    return redirect(url_for('index'))


@app.route('/add_dummy_row')
def add_dummy_row():
    try:
        # Create a dummy RealEstateListing instance
        dummy_listing = RealEstateListing(
            booli_price=1000000,
            boarea=100,
            rum=4,
            biarea=20,
            tomtstorlek=500,
            byggar=2000,
            utgangspris=900000,
            bostadstyp='Villa',
            omrade='Dummy Area',
            stad='Dummy City',
            price_text='1,000,000 SEK',
            url='http://example.com/dummy-listing'
        )

        # Store the dummy listing in the database
        dummy_listing.storeInDB()

        flash("Dummy row added successfully.", "success")
    except Exception as e:
        flash(f"An error occurred while adding the dummy row: {str(e)}", "danger")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)