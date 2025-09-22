from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from .models import Product, Order, OrderItem
from django.http import HttpResponse

def product_list(request):
    products = Product.objects.all()
    return render(request, 'store/product_list.html', {'products': products})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'store/product_detail.html', {'product': product})

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    request.session['cart'] = cart
    return redirect('product_list')

def cart_detail(request):
    cart = request.session.get('cart', {})
    products = []
    total = 0
    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=product_id)
        subtotal = product.price * quantity
        total += subtotal
        products.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    return render(request, 'store/cart.html', {'products': products, 'total': total})

def remove_from_cart(request, item_id):
    cart = request.session.get('cart', {})
    if str(item_id) in cart:
        del cart[str(item_id)]
    request.session['cart'] = cart
    return redirect('cart_detail')

def checkout(request):
    if not request.user.is_authenticated:
        return redirect('login')
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('product_list')
    order = Order.objects.create(user=request.user)
    total = 0
    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=product_id)
        price = product.price * quantity
        OrderItem.objects.create(order=order, product=product, quantity=quantity, price=price)
        total += price
    order.total_price = total
    order.save()
    del request.session['cart']
    return HttpResponse("Order placed successfully! Order ID: " + str(order.id))

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'store/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('product_list')
        else:
            messages.error(request, 'Invalid credentials')
    return render(request, 'store/login.html')

def user_logout(request):
    logout(request)
    return redirect('product_list')