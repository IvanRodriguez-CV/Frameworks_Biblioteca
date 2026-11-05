from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from biblioteca.views import (
    AuthorViewSet,
    BookCopyViewSet,
    BookViewSet,
    CategoryViewSet,
    LibraryTokenObtainPairView,
    LibraryTokenRefreshView,
    CurrentUserView,
    LoanViewSet,
    RegisterView,
    UserViewSet,
    library_home,
)

router = DefaultRouter()
router.register("authors", AuthorViewSet, basename="author")
router.register("categories", CategoryViewSet, basename="category")
router.register("books", BookViewSet, basename="book")
router.register("copies", BookCopyViewSet, basename="copy")
router.register("loans", LoanViewSet, basename="loan")
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("", library_home, name="library-home"),
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/token/", LibraryTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", LibraryTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", CurrentUserView.as_view(), name="current_user"),
    path("api/", include(router.urls)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
