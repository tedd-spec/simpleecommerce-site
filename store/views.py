from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from .models import Product, Order, OrderItem, Category
import json
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def home(request):
    """Home page view"""
    # Get featured products
    featured_products = Product.objects.filter(is_featured=True).select_related('category')[:8]
    if not featured_products.exists():
        featured_products = Product.objects.all().select_related('category')[:8]
    
    context = {
        'products': featured_products,
    }
    return render(request, 'store/home.html', context)
def clear_cart(request):
    """
    Clear all items from the user's cart
    """
    if request.user.is_authenticated:
        # Clear cart for authenticated user
        Cart.objects.filter(user=request.user).delete()
        messages.success(request, 'Your cart has been cleared!')
    else:
        # Clear cart from session for anonymous user
        request.session['cart'] = {}
        messages.success(request, 'Your cart has been cleared!')
    
    return redirect('store:cart')

def product_list(request):
    """Product list view with pagination and filtering"""
    products = Product.objects.all().select_related('category')
    query = request.GET.get('q')
    category_slug = request.GET.get('category')
    page = request.GET.get('page', 1)
    verified_only = request.GET.get('verified', '0') == '1'
    in_stock = request.GET.get('stock', '0') == '1'
    
    if query:
        products = products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(brand__icontains=query)
        )
    
    if category_slug and category_slug != 'all':
        products = products.filter(category__slug=category_slug)
    
    if verified_only:
        products = products.filter(is_verified=True)
    
    if in_stock:
        products = products.filter(stock__gt=0)
    
    # Pagination
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(page)
    
    # Get all categories for filter
    categories = Category.objects.all()
    
    context = {
        'products': page_obj,
        'categories': categories,
        'query': query,
        'selected_category': category_slug,
        'verified_only': verified_only,
        'in_stock': in_stock,
    }
    return render(request, 'store/product_list.html', context)

def product_detail(request, pk):
    """Product detail view"""
    product = get_object_or_404(Product, pk=pk)
    
    # Get related products (same category, exclude current)
    related_products = Product.objects.filter(
        category=product.category,
        pk__ne=pk,
        is_featured=True
    ).select_related('category')[:4]
    
    if not related_products.exists():
        related_products = Product.objects.filter(
            category=product.category,
            pk__ne=pk
        ).select_related('category')[:4]
    
    # Calculate average rating (placeholder)
    average_rating = 4.8
    
    context = {
        'product': product,
        'related_products': related_products,
        'average_rating': average_rating,
    }
    return render(request, 'store/product_detail.html', context)

@require_http_methods(["GET", "POST"])
def add_to_cart(request, product_id):
    """Add product to cart"""
    if not request.session.session_key:
        request.session.create()
    
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.GET.get('quantity', request.POST.get('quantity', 1)))
    
    # Check stock
    if quantity > product.stock:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': f'Only {product.stock} items available in stock'
            })
        messages.error(request, f'Only {product.stock} items available in stock')
        return redirect('product_detail', pk=product_id)
    
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    
    if product_id_str in cart:
        new_quantity = cart[product_id_str] + quantity
        if new_quantity > product.stock:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Cannot exceed stock limit of {product.stock}'
                })
            messages.error(request, f'Cannot add more than {product.stock} items')
            return redirect('product_detail', pk=product_id)
        cart[product_id_str] = new_quantity
    else:
        cart[product_id_str] = quantity
    
    request.session['cart'] = cart
    request.session.modified = True
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': f'Added {quantity} x {product.name} to cart',
            'cart_count': sum(cart.values()),
            'cart_items': len(cart),
            'product_name': product.name,
            'total_price': float(product.price) * quantity
        })
    
    messages.success(request, f'Added {quantity} x {product.name} to cart!')
    return redirect(request.META.get('HTTP_REFERER', 'product_list'))

def cart_detail(request):
    """Cart detail view"""
    cart = request.session.get('cart', {})
    products = []
    total = 0
    tax_rate = 0.08  # 8% tax
    
    for product_id, quantity in list(cart.items()):
        try:
            product = Product.objects.get(id=product_id)
            if quantity > product.stock:
                # Adjust quantity to available stock
                cart[str(product_id)] = product.stock
                quantity = product.stock
                request.session['cart'] = cart
                request.session.modified = True
                messages.warning(request, f'Quantity for {product.name} adjusted to available stock: {quantity}')
            
            subtotal = float(product.price) * quantity
            total += subtotal
            products.append({
                'product': product,
                'quantity': quantity,
                'subtotal': round(subtotal, 2),
                'unit_price': float(product.price)
            })
        except Product.DoesNotExist:
            # Remove invalid product from cart
            if str(product_id) in cart:
                del cart[str(product_id)]
            request.session['cart'] = cart
            request.session.modified = True
            messages.warning(request, 'Some items were removed from your cart')
    
    # Calculate tax and final total
    tax_amount = round(total * tax_rate, 2)
    final_total = round(total + tax_amount, 2)
    
    context = {
        'products': products,
        'total': round(total, 2),
        'tax_amount': tax_amount,
        'final_total': final_total,
        'tax_rate': tax_rate,
        'cart_count': len(products),
        'cart_items': sum(cart.values()) if cart else 0
    }
    return render(request, 'store/cart.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def update_cart_quantity(request, product_id):
    """Update cart item quantity via AJAX"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'status': 'error', 'message': 'AJAX request required'}, status=400)
    
    cart = request.session.get('cart', {})
    quantity = int(request.POST.get('quantity', 1))
    product_id_str = str(product_id)
    
    try:
        product = Product.objects.get(id=product_id)
        if quantity > product.stock:
            quantity = product.stock
            messages.warning(request, f'Quantity adjusted to available stock: {quantity}')
        
        if quantity <= 0:
            if product_id_str in cart:
                del cart[product_id_str]
                messages.success(request, f'{product.name} removed from cart')
        else:
            cart[product_id_str] = quantity
            messages.success(request, f'Updated quantity to {quantity}')
        
        request.session['cart'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'status': 'success',
            'quantity': quantity,
            'cart_count': sum(cart.values()),
            'cart_items': len([q for q in cart.values() if q > 0]),
            'message': f'Cart updated successfully'
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Product not found'
        })

def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart = request.session.get('cart', {})
    product_id_str = str(item_id)
    
    if product_id_str in cart:
        try:
            product = Product.objects.get(id=item_id)
            del cart[product_id_str]
            request.session['cart'] = cart
            request.session.modified = True
            messages.success(request, f'{product.name} removed from cart')
        except Product.DoesNotExist:
            del cart[product_id_str]
            request.session['cart'] = cart
            request.session.modified = True
            messages.success(request, 'Item removed from cart')
    else:
        messages.warning(request, 'Item not found in cart')
    
    return redirect('cart_detail')

def checkout(request):
    """Process checkout"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to checkout')
        return redirect(f'{settings.LOGIN_URL}?next={request.path}')
    
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, 'Your cart is empty')
        return redirect('product_list')
    
    # Validate stock before creating order
    valid_items = []
    total = 0
    
    for product_id, quantity in list(cart.items()):
        try:
            product = Product.objects.get(id=product_id)
            if quantity <= product.stock:
                price = float(product.price) * quantity
                valid_items.append((product, quantity, price))
                total += price
            else:
                # Remove out-of-stock items
                del cart[product_id]
                messages.warning(request, f'{product.name} removed - insufficient stock')
        except Product.DoesNotExist:
            del cart[product_id]
            continue
    
    if not valid_items:
        request.session['cart'] = {}
        request.session.modified = True
        messages.error(request, 'All items in cart are out of stock')
        return redirect('product_list')
    
    # Create order
    order = Order.objects.create(
        user=request.user,
        total_price=round(total, 2),
        status='confirmed'
    )
    
    # Create order items
    for product, quantity, price in valid_items:
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=round(price / quantity, 2)  # Store unit price
        )
    
    # Clear cart
    request.session['cart'] = {}
    request.session.modified = True
    
    # Send confirmation email (optional)
    try:
        send_mail(
            subject=f'Order #{order.id} Confirmation - YourStore',
            message=f'Thank you for your order! Your order #{order.id} has been received and is being processed.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f'Failed to send order confirmation email: {e}')
    
    messages.success(request, f'Thank you! Order #{order.id} placed successfully. Total: ${total:.2f}')
    return redirect('order_confirmation', order_id=order.id)

def order_confirmation(request, order_id):
    """Order confirmation page"""
    if not request.user.is_authenticated:
        return redirect(f'{settings.LOGIN_URL}?next={request.path}')
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    tax_rate = 0.08
    tax_amount = round(float(order.total_price) * tax_rate, 2)
    final_total = round(float(order.total_price) + tax_amount, 2)
    
    context = {
        'order': order,
        'order_items': order.items.select_related('product').all(),
        'tax_amount': tax_amount,
        'final_total': final_total,
        'tax_rate': tax_rate
    }
    return render(request, 'store/order_confirmation.html', context)

def register(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('product_list')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        email = request.POST.get('email', '')
        
        if form.is_valid():
            user = form.save(commit=False)
            user.email = email
            user.save()
            messages.success(request, 'Account created successfully! Welcome to YourStore!')
            
            # Log user in automatically
            user = authenticate(username=user.username, password=request.POST['password1'])
            if user:
                login(request, user)
                messages.info(request, f'Welcome, {user.username}! Your account is ready.')
                return redirect('product_list')
            else:
                return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    
    context = {'form': form}
    return render(request, 'store/register.html', context)

def user_login(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('product_list')
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next', 'product_list')
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    
    return render(request, 'store/login.html')

def user_logout(request):
    """User logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully. See you soon!')
    return redirect('home')