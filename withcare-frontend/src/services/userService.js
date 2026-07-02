// Persistent anonymous user identity stored in localStorage

export function getUserId() {
  let id = localStorage.getItem('withcare_user_id');
  if (!id) {
    id = 'u-' + Math.random().toString(36).slice(2, 10) + '-' + Date.now();
    localStorage.setItem('withcare_user_id', id);
  }
  return id;
}
