from django.shortcuts import render, HttpResponse

def index(request):

    return HttpResponse("Hello")

def hi(request):
    return HttpResponse("hello ")
