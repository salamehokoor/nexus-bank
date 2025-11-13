from django.urls import path
from .views import AccountsListCreateView, AccountCardsListCreateView  #ActivateUserView
from rest_framework.routers import DefaultRouter
from .views import AccountsListCreateView, AccountCardsListCreateView, InternalTransferListCreateView, ExternalTransferListCreateView, BillPaymentListCreateView, GoogleLogin, BillPaymentDetailView

urlpatterns = [
    path("accounts", AccountsListCreateView.as_view(), name="accounts-list"),
    ###
    path("accounts/<str:account_number>/cards/",
         AccountCardsListCreateView.as_view(),
         name="account-cards"),
    ###

    #path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    ###
    path("transfers/internal/",
         InternalTransferListCreateView.as_view(),
         name="transfer-internal"),
    ###
    path("transfers/external/",
         ExternalTransferListCreateView.as_view(),
         name="transfer-external"),
    ###
    path("bill/", BillPaymentListCreateView.as_view(), name="bill-list"),
    ###
    path("bill/<int:pk>/", BillPaymentDetailView.as_view(),
         name="bill-detail"),
    ###
    #path(
    #   "auth/users/activation/<uid>/<token>/",
    #   ActivateUserView.as_view(),
    #  name="user-activation-click",
    #),
]
