import streamlit as st
import logging
from database import (add_product, add_transaction, get_current_quantity,
                      get_last_price_before_date, get_last_purchase_date, get_purchase_history,
                      get_all_products, get_product_id, get_transactions_by_date, delete_transaction,
                      get_daily_transactions, calculate_daily_earnings, estimate_daily_needs)
from datetime import datetime, date
from typing import Optional, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Helper function to format date/time in 12-hour format
def format_date_time(date_time_str: Optional[str]) -> Optional[str]:
    if not date_time_str:
        return None
    try:
        dt = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y, %I:%M %p")
    except ValueError:
        return date_time_str

st.title("ShopEase - Grocery Inventory Management")

# Sidebar menu
menu = ["View Inventory", "Add Purchase", "Daily Cash Flow", "Search Product",
        "Daily Listings", "Daily Summary", "Historical Price Lookup"]
choice = st.sidebar.selectbox("Menu", menu)

unit_options = ["kg", "grams", "kilograms", "quintal", "tons", "liters", "milliliters", "pieces", "packets"]

# Pages
if choice == "View Inventory":
    st.subheader("Current Inventory")
    products = get_all_products()
    if not products:
        st.write("No products in inventory.")
    else:
        for product in products:
            product_id, name, unit = product
            quantity = get_current_quantity(product_id)
            last_price = get_last_price_before_date(product_id)
            last_date = get_last_purchase_date(product_id)
            st.write(f"- {name}: {quantity} {unit}, Last Purchase Date: {format_date_time(last_date) if last_date else 'N/A'}, Last Price: {last_price if last_price else 'N/A'} INR")

elif choice == "Add Purchase":
    st.subheader("Add Purchase")
    if 'product_name' not in st.session_state:
        st.session_state.product_name = ""
    if 'unit' not in st.session_state:
        st.session_state.unit = unit_options[0]
    if 'quantity' not in st.session_state:
        st.session_state.quantity = 0.0
    if 'price' not in st.session_state:
        st.session_state.price = 0.0
    if 'show_success' not in st.session_state:
        st.session_state.show_success = False

    product_name = st.text_input("Product Name (e.g., চিনি/Sugar)", value=st.session_state.product_name)
    unit = st.selectbox("Unit", unit_options, index=unit_options.index(st.session_state.unit))
    quantity = st.number_input("Quantity Purchased", min_value=0.0, step=0.1, value=st.session_state.quantity)
    price = st.number_input("Price per Unit (INR)", min_value=0.0, step=0.1, value=st.session_state.price)

    if st.button("Add Purchase"):
        if not product_name:
            st.error("Please enter product name.")
        elif quantity <= 0:
            st.error("Quantity must be greater than 0.")
        elif price <= 0:
            st.error("Price must be greater than 0.")
        else:
            product_id = get_product_id(product_name)
            if not product_id:
                add_product(product_name, unit)
                product_id = get_product_id(product_name)
            add_transaction(product_id, quantity, price)
            st.session_state.show_success = True
            st.session_state.product_name = ""
            st.rerun()

    if st.session_state.show_success:
        st.success("Product added successfully!")
        st.session_state.show_success = False

elif choice == "Daily Cash Flow":
    st.subheader("Daily Cash Flow")
    selected_date = st.date_input("Select Date", value=date.today())
    
    cash_in = st.number_input("Cash In Today (INR)", min_value=0.0, step=0.1)
    cash_out = st.number_input("Cash Out Today (INR)", min_value=0.0, step=0.1)
    
    if st.button("Calculate Daily Profit/Loss"):
        if cash_in < 0 or cash_out < 0:
            st.error("Cash values cannot be negative.")
        else:
            purchase_costs = -calculate_daily_earnings(selected_date)
            total_cash_out = cash_out + purchase_costs
            profit_loss = cash_in - total_cash_out
            
            st.write(f"**Date:** {selected_date}")
            st.write(f"**Cash In:** {cash_in:.2f} INR")
            st.write(f"**Cash Out (Manual):** {cash_out:.2f} INR")
            st.write(f"**Purchase Costs:** {purchase_costs:.2f} INR")
            st.write(f"**Total Cash Out:** {total_cash_out:.2f} INR")
            st.write(f"**Profit/Loss:** {profit_loss:.2f} INR")
            if profit_loss >= 0:
                st.success(f"Profit: {profit_loss:.2f} INR")
            else:
                st.error(f"Loss: {abs(profit_loss):.2f} INR")

elif choice == "Search Product":
    st.subheader("Search Product")
    search_term = st.text_input("Enter Product Name (e.g., Rice, চিনি/Sugar)")
    selected_date = st.date_input("Filter by Date (optional)", value=None, min_value=date(2020, 1, 1), key="search_date")
    
    if st.button("Search"):
        if not search_term.strip():
            st.error("Please enter a product name.")
        else:
            normalized_search = search_term.strip().lower()
            product_id = get_product_id(normalized_search)
            
            if not product_id:
                products = get_all_products()
                found = False
                for p_id, name, unit in products:
                    if normalized_search in name.lower():
                        product_id = p_id
                        found = True
                        break
                if not found:
                    st.write("No products found.")
                else:
                    name = [p[1] for p in products if p[0] == product_id][0]
                    unit = [p[2] for p in products if p[0] == product_id][0]
                    quantity = get_current_quantity(product_id)
                    last_price = get_last_price_before_date(product_id)
                    last_date = get_last_purchase_date(product_id)
                    st.write(f"**{name}**")
                    st.write(f"- Current Quantity: {quantity} {unit}")
                    st.write(f"- Last Purchase Date: {format_date_time(last_date) if last_date else 'N/A'}")
                    st.write(f"- Last Price: {last_price if last_price else 'N/A'} INR")
                    
                    # Show purchase history with optional date filter
                    st.subheader("Purchase History")
                    history = get_purchase_history(product_id)
                    if not history:
                        st.write("No purchase history available.")
                    else:
                        filtered_history = history
                        if selected_date:
                            filtered_history = [
                                (date, qty, price) for date, qty, price in history
                                if datetime.strptime(date, "%Y-%m-%d %H:%M:%S").date() == selected_date
                            ]
                            if not filtered_history:
                                st.write(f"No purchases found for {name} on {selected_date}.")
                        
                        for purchase_date, qty, price in filtered_history:
                            st.write(f"- Date: {format_date_time(purchase_date)}, Quantity: {qty} {unit}, Price: {price} INR")
            else:
                name = [p[1] for p in get_all_products() if p[0] == product_id][0]
                unit = [p[2] for p in get_all_products() if p[0] == product_id][0]
                quantity = get_current_quantity(product_id)
                last_price = get_last_price_before_date(product_id)
                last_date = get_last_purchase_date(product_id)
                st.write(f"**{name}**")
                st.write(f"- Current Quantity: {quantity} {unit}")
                st.write(f"- Last Purchase Date: {format_date_time(last_date) if last_date else 'N/A'}")
                st.write(f"- Last Price: {last_price if last_price else 'N/A'} INR")
                
                # Show purchase history with optional date filter
                st.subheader("Purchase History")
                history = get_purchase_history(product_id)
                if not history:
                    st.write("No purchase history available.")
                else:
                    filtered_history = history
                    if selected_date:
                        filtered_history = [
                            (date, qty, price) for date, qty, price in history
                            if datetime.strptime(date, "%Y-%m-%d %H:%M:%S").date() == selected_date
                        ]
                        if not filtered_history:
                            st.write(f"No purchases found for {name} on {selected_date}.")
                    
                    for purchase_date, qty, price in filtered_history:
                        st.write(f"- Date: {format_date_time(purchase_date)}, Quantity: {qty} {unit}, Price: {price} INR")

elif choice == "Daily Listings":
    st.subheader("Daily Listings")
    selected_date = st.date_input("Select Date", value=date.today())
    transactions = get_transactions_by_date(selected_date)
    if not transactions:
        st.write("No purchases on this date.")
    else:
        st.write(f"Purchases on {selected_date}:")
        for trans in transactions:
            trans_id, name, quantity, price, unit, trans_date = trans
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"- {name}: {quantity} {unit} at {price} INR on {format_date_time(trans_date)}")
            with col2:
                if st.button("Delete", key=f"del_{trans_id}"):
                    success, message = delete_transaction(trans_id)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

elif choice == "Daily Summary":
    st.subheader("Daily Summary")
    selected_date = st.date_input("Select Date for Summary", value=date.today())
    earnings = calculate_daily_earnings(selected_date)
    needs = estimate_daily_needs(selected_date)
    
    st.write(f"**Daily Earnings on {selected_date}: {earnings:.2f} INR**")
    st.write("**Estimated Product Needs:**")
    for product, qty in needs.items():
        unit = [p[2] for p in get_all_products() if p[1] == product][0]
        st.write(f"- {product}: {qty:.2f} {unit}")

elif choice == "Historical Price Lookup":
    st.subheader("Historical Price Lookup")
    product_name = st.text_input("Product Name (e.g., চিনি/Sugar)")
    selected_date = st.date_input("Select Date", value=date.today())
    if st.button("Search Price"):
        if not product_name:
            st.error("Please enter a product name.")
        else:
            product_id = get_product_id(product_name)
            if not product_id:
                st.error("Product not found.")
            else:
                target_date = f"{selected_date} 23:59:59"
                price = get_last_price_before_date(product_id, target_date)
                if price:
                    st.success(f"Price of {product_name} on {selected_date}: {price} INR")
                else:
                    st.warning(f"No purchase found for {product_name} on or before {selected_date}.")
