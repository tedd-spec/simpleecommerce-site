from .models import Product

def cart_count(request):
    """Add cart count to all templates"""
    if not request.session.session_key:
        request.session.create()
    
    cart = request.session.get('cart', {})
    cart_count = 0
    
    # Validate cart items
    valid_cart = {}
    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(id=product_id)
            if quantity <= product.stock:
                valid_cart[product_id] = quantity
                cart_count += quantity
            else:
                # Adjust to available stock
                valid_cart[product_id] = product.stock
                cart_count += product.stock
        except Product.DoesNotExist:
            # Remove invalid product
            continue
    
    # Update session if needed
    if valid_cart != cart:
        request.session['cart'] = valid_cart
        request.session.modified = True
    
    return {
        'cart_count': cart_count,
        'cart_items': len(valid_cart)
    }