import { useState, useCallback } from 'react';
import type { Notification } from '../types';

let notificationId = 0;

export const useNotifications = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = useCallback((type: Notification['type'], message: string) => {
    const id = String(++notificationId);
    const newNotification: Notification = {
      id,
      type,
      message,
      created_at: new Date().toISOString(),
    };

    setNotifications((prev) => [...prev, newNotification]);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 5000);

    return id;
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const success = useCallback((message: string) => {
    return addNotification('success', message);
  }, [addNotification]);

  const error = useCallback((message: string) => {
    return addNotification('error', message);
  }, [addNotification]);

  const info = useCallback((message: string) => {
    return addNotification('info', message);
  }, [addNotification]);

  const warning = useCallback((message: string) => {
    return addNotification('warning', message);
  }, [addNotification]);

  return {
    notifications,
    addNotification,
    removeNotification,
    success,
    error,
    info,
    warning,
  };
};

export type NotificationContextType = ReturnType<typeof useNotifications>;
