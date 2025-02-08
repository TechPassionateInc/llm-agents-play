import streamlit as st
from autogen import AssistantAgent, UserProxyAgent
import yfinance as yf
from datetime import datetime, timedelta
import os

# Accessing API keys
openai_api_key = st.secrets["api_keys"]["openai_api_key"]

# LLM Configuration
llm_config = {
    "model": "gpt-4",
    "api_key": openai_api_key,
    "cache": None,
    "temperature": 0,
}

# Function to fetch real-time options data for multiple expiration dates
def fetch_option_data(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    current_price = ticker.history(period="1d")['Close'].iloc[-1]

    expiration_dates = ticker.options
    if not expiration_dates:
        return f"No options data available for {ticker_symbol}."

    # Filter expiration dates within the next 2 months
    today = datetime.today()
    two_months_later = today + timedelta(days=60)
    filtered_expirations = [
        date for date in expiration_dates 
        if today <= datetime.strptime(date, "%Y-%m-%d") <= two_months_later
    ]

    if not filtered_expirations:
        return f"No options data available for the next 2 months for {ticker_symbol}."

    options_data = {}

    # Fetch options data for each expiration date
    for expiration_date in filtered_expirations:
        option_chain = ticker.option_chain(expiration_date)
        calls_data = option_chain.calls[['contractSymbol', 'strike', 'lastPrice', 'impliedVolatility']]
        puts_data = option_chain.puts[['contractSymbol', 'strike', 'lastPrice', 'impliedVolatility']]

        options_data[expiration_date] = {
            "calls": calls_data.to_dict(orient='records'),
            "puts": puts_data.to_dict(orient='records'),
        }

    return {
        "current_price": current_price,
        "options_data": options_data,
        "expiration_dates": filtered_expirations
    }

# Financial Research Assistant AI Agent
financial_research_agent = AssistantAgent(
    name="FinancialResearchAgent",
    llm_config=llm_config,
    system_message=(
        "You are a Financial Research Assistant specializing in stock option strategies. For the provided ticker symbols, analyze the current option chain data and identify profitable Covered Call opportunities. Focus on options with near-term expiration (2-4 weeks) and strike prices slightly above the current stock price (out-of-the-money). Consider the following factors in your analysis: option premium, implied volatility, potential capital gains, and assignment risk. Provide key metrics such as annualized return, breakeven price, and the likelihood of assignment. Recommend the best Covered Call trades with a balance of income and risk."
        # "You are a Financial Research Assistant specialized in analyzing stock options for given tickers. "
        # "You will receive real-time options data for multiple expiration dates within the next 2 months. "
        # "Analyze the options chain data provided for profitable Covered Call and Cash-Secured Put opportunities. "
        # "Consider factors like option premiums, strike prices, implied volatility, and current stock prices. "
        # "Provide key metrics like annualized return, breakeven points, and assignment risks in your recommendations."
    ),
)

# Reviewer AI Agent
reviewer_agent = AssistantAgent(
    name="ReviewerAgent",
    llm_config=llm_config,
    system_message=(
        "You are a Reviewer specializing in validating the accuracy and profitability of financial research outputs related to stock options. "
        "You will receive real-time options data and the Financial Research Assistant's recommendations. "
        "Verify the accuracy of option premiums, strike prices, expiration dates, and implied volatility. "
        "Recalculate annualized returns, breakeven points, and assignment risks to confirm profitability, and flag any discrepancies."
    ),
)

# User Agent to initiate and receive responses
user_agent = UserProxyAgent(
    name="User",
    human_input_mode="NEVER",
)

# Streamlit UI Components
st.title("Multi-Expiration Stock Options Analyzer")

# User input for ticker symbol
ticker_input = st.text_input("Enter Stock Ticker Symbol (e.g., AAPL, MSFT):")
analyze_button = st.button('Analyze')

if analyze_button and ticker_input:
    with st.spinner("Fetching data and analyzing..."):
        # Fetch data for the entered ticker symbol
        ticker = ticker_input.upper().strip()
        fetched_data = fetch_option_data(ticker)

        if isinstance(fetched_data, str):
            st.error(fetched_data)
        else:
            # Display fetched data
            st.subheader(f"Options Data for {ticker}")
            st.markdown(f"**Current Price:** ${fetched_data['current_price']:.2f}")
            st.markdown("**Analyzing Expiration Dates (Next 2 Months):**")
            st.write(fetched_data['expiration_dates'])

            # Display options data for each expiration date
            for expiration_date, data in fetched_data['options_data'].items():
                st.markdown(f"### Expiration Date: {expiration_date}")
                
                # Display first 5 call options
                st.markdown("**Call Options (Top 5):**")
                for call in data['calls'][:5]:
                    st.write(call)

                # Display first 5 put options
                st.markdown("**Put Options (Top 5):**")
                for put in data['puts'][:5]:
                    st.write(put)

            # Create message for AI agents
            message = (
                f"Analyze the following options data for {ticker} to identify profitable Covered Call and Cash-Secured Put opportunities.\n\n"
                f"Ticker: {ticker}\nCurrent Price: ${fetched_data['current_price']:.2f}\n"
                f"Expiration Dates: {', '.join(fetched_data['expiration_dates'])}\n"
            )
            for expiration_date, data in fetched_data['options_data'].items():
                message += f"\nExpiration Date: {expiration_date}\n"
                message += f"\nCalls:\n{data['calls'][:5]}\n"
                message += f"\nPuts:\n{data['puts'][:5]}\n"

            # Initiate the conversation between agents
            chat_result = user_agent.initiate_chat(
                financial_research_agent,
                message=message,
                recipients=[reviewer_agent],
                max_turns=2  # Increased for more detailed multi-expiration analysis
            )

            # Display the full chat history
            st.subheader("Chat History")
            for idx, msg in enumerate(chat_result.chat_history):
                role = msg.get("role", "system").capitalize()
                content = msg.get("content", "")
                st.markdown(f"**{role}:** {content}\n---")

else:
    st.info("Please enter a stock ticker symbol and click 'Analyze' to get started.")