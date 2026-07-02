import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatThread from './components/ChatThread';
import LoginScreen from './components/LoginScreen';
import ProfileModal from './components/ProfileModal';
import TasksView from './components/views/TasksView';
import PlansView from './components/views/PlansView';
import { useChat, dbMsgToUiMsg } from './hooks/useChat';
import { getStoredUser, signOut } from './services/authService';
import { getLocation, setStoredLocation } from './services/locationService';
import { fetchProfiles, createProfile, updateProfile, deleteProfile } from './services/profileApi';
import {
  fetchConversations,
  fetchMessages,
  saveMessage,
  deleteConversation,
} from './services/conversationApi';

const ACCENT = '#1C7A6A';

export default function App() {
  const [user, setUser] = useState(getStoredUser());

  const [collapsed,       setCollapsed]       = useState(false);
  const [activeView,      setActiveView]      = useState('chat'); // chat | tasks | plans
  const [profiles,        setProfiles]        = useState([]);
  const [activeProfileId, setActiveProfileId] = useState(null);
  const [modal,           setModal]           = useState(null); // null | 'new' | profileObj
  const [conversations,   setConversations]   = useState([]);
  const [activeConvId,    setActiveConvId]    = useState(null);
  const [loadingConv,     setLoadingConv]     = useState(false);
  const [userLocation,    setUserLocation]    = useState({ city: '', lat: null, lng: null });

  const pendingConvId = useRef(null);
  const userId = user?.id;

  const activeProfile = profiles.find(p => p.id === activeProfileId) || profiles[0] || null;

  // ── Save callback passed to useChat ─────────────────────────────────────────
  const handleSave = useCallback(async ({ role, content, carePlan }) => {
    if (!userId) return;

    // Create the conversation exactly once per new chat — the id is generated and the ref
    // set SYNCHRONOUSLY, so a fast assistant/clarify save can't race the user save into a
    // second conversation. Only user messages ever set a title (never assistant replies).
    let convId = pendingConvId.current;
    if (!convId) {
      convId = 'c-' + ((crypto.randomUUID && crypto.randomUUID()) || Math.random().toString(36).slice(2) + Date.now());
      pendingConvId.current = convId;
      setActiveConvId(convId);
      setConversations(prev => [{
        id: convId,
        title: role === 'user' ? content.slice(0, 70) : 'New conversation',
        profile_name: activeProfile?.name || 'You',
        updated_at: new Date().toISOString(),
      }, ...prev]);
    }

    await saveMessage(userId, convId, {
      role, content, carePlan,
      title: role === 'user' ? content.slice(0, 70) : undefined,
      profileName: activeProfile?.name || 'You',
    });

    if (role === 'user') {
      setConversations(prev => prev.map(c =>
        c.id === convId
          ? { ...c, title: c.title === 'New conversation' ? content.slice(0, 70) : c.title, updated_at: new Date().toISOString() }
          : c
      ));
    }
  }, [userId, activeProfile]);

  const { messages, input, setInput, send, reset, onKey, msgVM } = useChat({
    onSave: handleSave,
    location: userLocation,
    profile: activeProfile,
    userId,
  });

  // ── Load profiles + conversations + location once signed in ──────────────────
  useEffect(() => {
    if (!userId) return;
    fetchProfiles(userId).then(list => {
      setProfiles(list);
      setActiveProfileId(prev => prev || (list[0] && list[0].id) || null);
    });
    fetchConversations(userId).then(setConversations);
    getLocation().then(loc => { if (loc) setUserLocation(loc); });
  }, [userId]);

  // ── Conversations ────────────────────────────────────────────────────────────
  const openConversation = useCallback(async (convId) => {
    setActiveView('chat');
    if (convId === activeConvId) return;
    setLoadingConv(true);
    setActiveConvId(convId);
    pendingConvId.current = convId;
    const dbMsgs = await fetchMessages(userId, convId);
    reset(dbMsgs.map(dbMsgToUiMsg), convId);
    setLoadingConv(false);
  }, [userId, activeConvId, reset]);

  const newChat = useCallback(() => {
    setActiveView('chat');
    pendingConvId.current = null;
    setActiveConvId(null);
    reset();
  }, [reset]);

  const removeConversation = useCallback(async (convId) => {
    await deleteConversation(userId, convId);
    setConversations(prev => prev.filter(c => c.id !== convId));
    if (activeConvId === convId) newChat();
  }, [userId, activeConvId, newChat]);

  // ── Location ─────────────────────────────────────────────────────────────────
  const editLocation = useCallback(() => {
    const city = window.prompt('Enter your city for "near me" searches:', userLocation.city || '');
    if (city && city.trim()) {
      const loc = { city: city.trim(), lat: null, lng: null };
      setStoredLocation(loc);
      setUserLocation(loc);
    }
  }, [userLocation.city]);

  // ── Profiles ─────────────────────────────────────────────────────────────────
  const switchProfile = useCallback((profileId) => {
    setActiveProfileId(profileId);
    newChat();
  }, [newChat]);

  const saveProfile = useCallback(async (data) => {
    if (modal && modal !== 'new' && modal.id) {
      const updated = await updateProfile(userId, modal.id, data);
      setProfiles(prev => prev.map(p => p.id === updated.id ? updated : p));
    } else {
      const created = await createProfile(userId, data);
      setProfiles(prev => [...prev, created]);
      setActiveProfileId(created.id);
    }
    setModal(null);
  }, [userId, modal]);

  const removeProfile = useCallback(async (profileId) => {
    if (!window.confirm('Delete this care profile?')) return;
    await deleteProfile(userId, profileId);
    setProfiles(prev => prev.filter(p => p.id !== profileId));
    if (activeProfileId === profileId) setActiveProfileId(null);
  }, [userId, activeProfileId]);

  const handleSignOut = useCallback(() => {
    signOut();
    setUser(null);
    setProfiles([]); setConversations([]); setActiveProfileId(null);
    pendingConvId.current = null;
    reset();
  }, [reset]);

  // ── Not signed in → login gate ───────────────────────────────────────────────
  if (!user) return <LoginScreen onLogin={setUser} />;

  // ── Profile view-models for the sidebar ──────────────────────────────────────
  const profileVMs = profiles.map(p => {
    const active = activeProfile?.id === p.id;
    const isPet = p.kind === 'pet';
    const primary = isPet
      ? (p.species || 'Pet')
      : (p.relation || (p.is_self ? 'Your own care' : ''));
    const meta = [primary, p.age ? `${p.age}` : ''].filter(Boolean).join(' · ');
    return {
      id: p.id,
      name: p.name,
      relation: meta,
      isPet,
      initials: (p.name || '?').trim().charAt(0).toUpperCase(),
      photo: p.photo || '',
      active,
      canEdit: true,          // everyone (including "You") can be edited
      canDelete: !p.is_self,  // ...but the self profile can't be deleted
      onClick: () => switchProfile(p.id),
      onEdit: () => setModal(p),
      onDelete: () => removeProfile(p.id),
      cardStyle: {
        display: 'flex', alignItems: 'center', gap: '11px', width: '100%',
        padding: '9px 11px', borderRadius: '13px', cursor: 'pointer',
        border: active ? `1px solid ${ACCENT}` : '1px solid #E6DFD2',
        background: active ? '#FFFFFF' : 'transparent',
        boxShadow: active ? '0 2px 8px rgba(40,30,20,0.05)' : 'none',
      },
      avatarStyle: {
        width: '34px', height: '34px', borderRadius: '50%', flex: '0 0 auto', overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '14px', fontWeight: 700,
        background: active ? ACCENT : '#EDE7DB', color: active ? '#fff' : '#8A8273',
      },
      railAvatarStyle: {
        width: '38px', height: '38px', borderRadius: '50%', border: 'none', cursor: 'pointer', overflow: 'hidden',
        fontSize: '14px', fontWeight: 700,
        background: active ? ACCENT : '#EDE7DB', color: active ? '#fff' : '#8A8273',
        boxShadow: active ? '0 0 0 3px rgba(28,122,106,0.22)' : 'none',
      },
    };
  });

  const sidebarW = collapsed ? '76px' : '292px';

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100%', overflow: 'hidden', fontFamily: "'Hanken Grotesk', system-ui, sans-serif", background: '#F6F2EC', color: '#26322F' }}>

      <aside style={{ width: sidebarW, flex: '0 0 auto', background: '#EDE8DF', borderRight: '1px solid #E2DACB', transition: 'width .28s ease', overflow: 'hidden' }}>
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed(v => !v)}
          profiles={profileVMs}
          onAddProfile={() => setModal('new')}
          conversations={conversations}
          activeConvId={activeConvId}
          onConvClick={openConversation}
          onConvDelete={removeConversation}
          onNewChat={newChat}
          activeView={activeView}
          onSelectView={setActiveView}
          user={user}
          onSignOut={handleSignOut}
          accent={ACCENT}
        />
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '16px 28px', borderBottom: '1px solid #EAE3D6' }}>
          {collapsed && (
            <button onClick={() => setCollapsed(false)} style={{ width: '34px', height: '34px', border: 'none', background: '#EFEAE0', borderRadius: '9px', color: '#6E7872', fontSize: '16px', cursor: 'pointer' }}>☰</button>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '13px', color: '#9A9485' }}>
              {activeView === 'tasks' ? 'Viewing' : activeView === 'plans' ? 'Viewing' : 'Managing care for'}
            </div>
            <div style={{ fontFamily: "'Newsreader', serif", fontSize: '18px', fontWeight: 500, color: '#26322F', lineHeight: 1.1 }}>
              {activeView === 'tasks' ? 'Tasks & Reminders' : activeView === 'plans' ? 'Workout & Diet Plans' : (activeProfile?.name || '—')}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              onClick={editLocation}
              title="Set your location for 'near me' searches"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '999px', background: '#F5F1EB', border: '1px solid #E4DCCE', cursor: 'pointer' }}
            >
              <span style={{ fontSize: '13px' }}>📍</span>
              <span style={{ fontSize: '12px', fontWeight: 500, color: userLocation.city ? '#6E7872' : '#B0A797' }}>
                {userLocation.city || 'Set location'}
              </span>
            </button>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '7px', padding: '7px 13px', borderRadius: '999px', background: '#EDF3F0', border: '1px solid #DCE8E2' }}>
              <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#2E8B6F' }} />
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#1C7A6A' }}>3 integrations connected</span>
            </div>
          </div>
        </header>

        {activeView === 'tasks' ? (
          <TasksView userId={userId} />
        ) : activeView === 'plans' ? (
          <PlansView userId={userId} />
        ) : loadingConv ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9A9485', fontSize: '14px' }}>
            Loading conversation...
          </div>
        ) : (
          <ChatThread
            messages={messages}
            input={input}
            setInput={setInput}
            send={send}
            onKey={onKey}
            msgVM={msgVM}
            accent={ACCENT}
          />
        )}
      </div>

      {modal && (
        <ProfileModal
          initial={modal === 'new' ? null : modal}
          onClose={() => setModal(null)}
          onSave={saveProfile}
        />
      )}
    </div>
  );
}
