import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchOrders, createOrder, cancelOrder, fetchFills } from '../api/orders';
import { OrderCreateRequest } from '../types/order';
import { useAppStore } from '../store';

export function useOrders(params?: { status?: string; symbol?: string; limit?: number }) {
  return useQuery({
    queryKey: ['orders', params],
    queryFn: () => fetchOrders(params),
    refetchInterval: 5000,
  });
}

export function useFills(params?: { order_id?: string; symbol?: string; limit?: number }) {
  return useQuery({
    queryKey: ['fills', params],
    queryFn: () => fetchFills(params),
    refetchInterval: 10000,
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((s) => s.addNotification);

  return useMutation({
    mutationFn: (order: OrderCreateRequest) => createOrder(order),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      addNotification({
        type: 'success',
        title: 'Order Created',
        message: `${data.side.toUpperCase()} ${data.quantity} ${data.symbol} order submitted`,
      });
    },
    onError: (error: Error) => {
      addNotification({
        type: 'error',
        title: 'Order Failed',
        message: error.message,
      });
    },
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((s) => s.addNotification);

  return useMutation({
    mutationFn: (orderId: string) => cancelOrder(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      addNotification({
        type: 'success',
        title: 'Order Cancelled',
        message: 'Order cancellation submitted',
      });
    },
    onError: (error: Error) => {
      addNotification({
        type: 'error',
        title: 'Cancel Failed',
        message: error.message,
      });
    },
  });
}
