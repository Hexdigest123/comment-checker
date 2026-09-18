import { useEffect } from 'react';
import type { Notification } from '../../types';

interface NotificationToastProps {
  notification: Notification;
  onRemove: (id: string) => void;
}

const notificationColors = {
  success: 'bg-green-500 text-white',
  error: 'bg-red-500 text-white',
  info: 'bg-blue-500 text-white',
  warning: 'bg-yellow-500 text-black',
};

export const NotificationToast: React.FC<NotificationToastProps> = ({ notification, onRemove }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onRemove(notification.id);
    }, 5000);

    return () => clearTimeout(timer);
  }, [notification.id, onRemove]);

  return (
    <div
      className={`fixed bottom-4 right-4 p-4 rounded-lg shadow-lg animate-fade-in ${notificationColors[notification.type]} max-w-sm z-50`}
      onClick={() => onRemove(notification.id)}
      style={{ cursor: 'pointer' }}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm">{notification.message}</span>
        <button
          className="ml-2 text-lg font-bold"
          onClick={(e) => {
            e.stopPropagation();
            onRemove(notification.id);
          }}
        >
          &times;
        </button>
      </div>
    </div>
  );
};

interface NotificationContainerProps {
  notifications: Notification[];
  onRemove: (id: string) => void;
}

export const NotificationContainer: React.FC<NotificationContainerProps> = ({ notifications, onRemove }) => {
  return (
    <>
      {notifications.map((notification) => (
        <NotificationToast
          key={notification.id}
          notification={notification}
          onRemove={onRemove}
        />
      ))}
    </>
  );
};
