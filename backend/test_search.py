from playwright.sync_api import sync_playwright
# Lets Python control a real, invisible web browser

def search_web(query):
    with sync_playwright() as p:
        # Start up the browser automation tool

        browser = p.chromium.launch(headless=True)
        # Launch an invisible Chrome browser

        page = browser.new_page()
        # Open a new browser tab

        page.goto(f"https://html.duckduckgo.com/html/?q={query}")
        # Go search DuckDuckGo for our query

        page.screenshot(path="debug_screenshot.png")
        # Take a screenshot of whatever the browser is actually seeing
        # This helps us "see" the page ourselves, since it's normally invisible

        content = page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        # Also save the raw webpage content as a text file, so we can inspect it closely if needed

        print("Screenshot and HTML saved. Check debug_screenshot.png")
        # Just confirms the files were created successfully

        browser.close()
        # Close the invisible browser

search_web("weather in London today")
# Run our test search