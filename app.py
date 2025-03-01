import streamlit as st
import logging
from database import (add_product, add_transaction, get_current_quantity,
                      get_last_price_before_date, get_last_purchase_date, get_purchase_history,
                      get_all_products, get_product_id, get_transactions_by_date, delete_transaction,
                      get_daily_transactions, calculate_daily_earnings, estimate_daily_needs,
                      save_daily_summary, get_daily_summary, delete_daily_summary)
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

unit_options = ["kg", "grams", "kilograms", "quintal", "tons", "liters", "milliliters", "pieces", "packets", "Chain", "box"]

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
            st.write(f"- {name}: {quantity} {unit}, Last Purchase Date: {format_date_time(last_date) if last_date else 'N/A'}, Last Total Cost: {last_price if last_price else 'N/A'} INR")

elif choice == "Add Purchase":
    st.subheader("Add Purchase")
    if 'product_name' not in st.session_state:
        st.session_state.product_name = ""
    if 'unit' not in st.session_state:
        st.session_state.unit = unit_options[0]
    if 'quantity' not in st.session_state:
        st.session_state.quantity = 0.0
    if 'total_purchase_cost' not in st.session_state:
        st.session_state.total_purchase_cost = 0.0
    if 'show_success' not in st.session_state:
        st.session_state.show_success = False

    product_name = st.text_input("Product Name (e.g., চিনি/Sugar)", value=st.session_state.product_name)
    unit = st.selectbox("Unit", unit_options, index=unit_options.index(st.session_state.unit) if st.session_state.unit in unit_options else 0)
    quantity = st.number_input("Quantity Purchased", min_value=0.0, step=0.1, value=st.session_state.quantity)
    total_purchase_cost = st.number_input("Total Purchase Cost (INR)", min_value=0.0, step=0.1, value=st.session_state.total_purchase_cost)

    if st.button("Add Purchase"):
        if not product_name.strip():
            st.error("Please enter product name.")
        elif quantity <= 0:
            st.error("Quantity must be greater than 0.")
        elif total_purchase_cost <= 0:
            st.error("Total purchase cost must be greater than 0.")
        else:
            product_id = get_product_id(product_name.strip())
            if not product_id:
                add_product(product_name.strip(), unit)
                product_id = get_product_id(product_name.strip())
            try:
                add_transaction(product_id, quantity, total_purchase_cost)
                st.session_state.show_success = True
                st.session_state.product_name = ""
                st.session_state.quantity = 0.0
                st.session_state.total_purchase_cost = 0.0
                st.session_state.unit = unit_options[0]
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add purchase: {e}")
                logger.error(f"Error adding purchase for {product_name}: {e}")

    if st.session_state.show_success:
        st.success("Product added successfully!")
        st.session_state.show_success = False

elif choice == "Daily Cash Flow":
    st.subheader("Daily Cash Flow")
    tab1, tab2 = st.tabs(["Calculate Today's Cash Flow", "View Historical Summary"])

    with tab1:
        selected_date = st.date_input("Select Date", value=date.today(), key="calc_date")
        cash_in = st.number_input("Cash In Today (INR)", min_value=0.0, step=0.1, key="cash_in")
        cash_out = st.number_input("Cash Out Today (INR)", min_value=0.0, step=0.1, key="cash_out")

        if st.button("Calculate Daily Profit/Loss", key="calc_button"):
            if cash_in < 0 or cash_out < 0:
                st.error("Cash values cannot be negative.")
            else:
                daily_earnings = calculate_daily_earnings(selected_date)
                purchase_costs = abs(daily_earnings) if daily_earnings < 0 else 0
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

                st.session_state.daily_summary = {
                    'selected_date': selected_date,
                    'cash_in': cash_in,
                    'cash_out': cash_out,
                    'purchase_costs': purchase_costs,
                    'profit_loss': profit_loss
                }

        if 'daily_summary' in st.session_state and st.button("Save This Summary", key="save_button"):
            try:
                summary = st.session_state.daily_summary
                save_daily_summary(
                    summary['selected_date'],
                    summary['cash_in'],
                    summary['cash_out'],
                    summary['purchase_costs'],
                    summary['profit_loss']
                )
                logger.info(f"Saved summary for {summary['selected_date']}: Cash In={summary['cash_in']}, Cash Out={summary['cash_out']}, Purchase Costs={summary['purchase_costs']}, Profit/Loss={summary['profit_loss']}")
                st.success(f"Summary saved successfully for {summary['selected_date']}!", icon="✅")
                st.session_state.cash_in = 0.0
                st.session_state.cash_out = 0.0
                del st.session_state.daily_summary
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save summary: {e}")
                logger.error(f"Error saving summary for {summary['selected_date']}: {e}")

    with tab2:
        view_date = st.date_input("Select Date to View Summary", value=date.today(), key="view_date")
        if st.button("View Summary", key="view_button"):
            try:
                summary = get_daily_summary(view_date)
                if summary:
                    cash_in, cash_out, purchase_costs, profit_loss = summary
                    total_cash_out = cash_out + purchase_costs
                    st.write(f"**Date:** {view_date}")
                    st.write(f"**Cash In:** {cash_in:.2f} INR")
                    st.write(f"**Cash Out (Manual):** {cash_out:.2f} INR")
                    st.write(f"**Purchase Costs:** {purchase_costs:.2f} INR")
                    st.write(f"**Total Cash Out:** {total_cash_out:.2f} INR")
                    st.write(f"**Profit/Loss:** {profit_loss:.2f} INR")
                    if profit_loss >= 0:
                        st.success(f"Profit: {profit_loss:.2f} INR")
                    else:
                        st.error(f"Loss: {abs(profit_loss):.2f} INR")
                    
                    if st.button("Delete Summary and Transactions", key=f"delete_summary_{view_date.isoformat()}"):
                        success, message = delete_daily_summary(view_date)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.warning(message)
                else:
                    # After deletion, don’t recalculate from transactions; just show no summary
                    st.warning(f"No summary saved for {view_date}. Transactions may exist but won’t be shown unless a summary is saved.")
                    logger.info(f"No summary found for {view_date}")
            except Exception as e:
                st.error(f"Error retrieving summary for {view_date}: {e}")
                logger.error(f"Error retrieving summary for {view_date}: {e}")

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
                    st.write(f"- Last Total Cost: {last_price if last_price else 'N/A'} INR")
                    
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
                            st.write(f"- Date: {format_date_time(purchase_date)}, Quantity: {qty} {unit}, Total Cost: {price:.2f} INR")
            else:
                name = [p[1] for p in get_all_products() if p[0] == product_id][0]
                unit = [p[2] for p in get_all_products() if p[0] == product_id][0]
                quantity = get_current_quantity(product_id)
                last_price = get_last_price_before_date(product_id)
                last_date = get_last_purchase_date(product_id)
                st.write(f"**{name}**")
                st.write(f"- Current Quantity: {quantity} {unit}")
                st.write(f"- Last Purchase Date: {format_date_time(last_date) if last_date else 'N/A'}")
                st.write(f"- Last Total Cost: {last_price if last_price else 'N/A'} INR")
                
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
                        st.write(f"- Date: {format_date_time(purchase_date)}, Quantity: {qty} {unit}, Total Cost: {price:.2f} INR")

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
                st.write(f"- {name}: {quantity} {unit} at {price:.2f} INR on {format_date_time(trans_date)}")
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
        if not product_name.strip():
            st.error("Please enter a product name.")
        else:
            product_id = get_product_id(product_name.strip())
            if not product_id:
                st.error("Product not found.")
            else:
                target_date = f"{selected_date} 23:59:59"
                price = get_last_price_before_date(product_id, target_date)
                if price is not None:
                    st.success(f"Total cost of {product_name} on {selected_date}: {price:.2f} INR")
                else:
                    st.warning(f"No purchase found for {product_name} on or before {selected_date}.")
