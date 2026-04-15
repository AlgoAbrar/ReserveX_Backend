class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related(
        'user', 'restaurant', 'branch', 'table'
    ).prefetch_related('menu_items__menu_item')

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    search_fields = ['booking_id', 'user__email', 'user__name', 'restaurant__name']
    ordering_fields = ['created_at', 'date', 'start_time', 'total_price', 'total_guests']
    ordering = ['-date', '-start_time']



    def _filter_by_role(self, queryset, user):
        if user.role == 'ADMIN':
            return queryset
        elif user.role == 'MANAGER':
            return queryset.filter(
                Q(restaurant__manager=user) | Q(user=user)
                ).distinct()
        return queryset.filter(user=user)

    def _send_notification(self, booking, notification_type):
        try:
            send_booking_notification(
                booking=booking,
                notification_type=notification_type,
                recipient=booking.user.email
            )
        except Exception as e:
            logger.error(f"Notification error: {str(e)}")

  

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Booking.objects.none()
        return self._filter_by_role(super().get_queryset(), user)

   

    serializer_map = {
        'list': BookingListSerializer,
        'create': BookingCreateSerializer,
        'update': BookingUpdateSerializer,
        'partial_update': BookingUpdateSerializer,
        'update_status': BookingStatusUpdateSerializer,
    }

    def get_serializer_class(self):
        return self.serializer_map.get(self.action, BookingDetailSerializer)

    

    permission_map = {
        'create': [IsAuthenticated],
        'list': [IsAuthenticated],
        'retrieve': [IsAuthenticated],
        'update': [IsAuthenticated, CanManageBookings],
        'partial_update': [IsAuthenticated, CanManageBookings],
        'destroy': [IsAuthenticated, CanManageBookings],
    }

    def get_permissions(self):
        return [perm() for perm in self.permission_map.get(self.action, [IsAuthenticated])]


    def perform_create(self, serializer):
        booking = serializer.save()
        self._send_notification(booking, 'CONFIRMATION')


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanManageBookings])
    def update_status(self, request, pk=None):
        booking = self.get_object()
        serializer = self.get_serializer(booking, data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            booking = serializer.save()

            status_map = {
                Booking.Status.CONFIRMED: 'CONFIRMATION',
                Booking.Status.REJECTED: 'REJECTION',
                Booking.Status.CANCELLED: 'CANCELLATION',
                Booking.Status.COMPLETED: 'COMPLETION',
                Booking.Status.EXPIRED: 'EXPIRY',
            }

            if booking.status in status_map:
                self._send_notification(booking, status_map[booking.status])

        return Response(BookingDetailSerializer(booking).data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        now = timezone.now()

        bookings = self.get_queryset().filter(
            Q(user=request.user) | Q(restaurant__manager=request.user),
            date__gte=now.date(),
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING_PAYMENT]
        ).exclude(
            date=now.date(), start_time__lt=now.time()
        ).order_by('date', 'start_time')[:10]

        return Response(BookingListSerializer(bookings, many=True).data)