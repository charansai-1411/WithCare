import React, { useState } from 'react';
import { CONNECTORS } from '../constants/agents';

function timeAgo(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr.replace(' ', 'T') + (isoStr.includes('T') ? '' : 'Z'));
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

function Avatar({ vm, style }) {
  return (
    <div style={style}>
      {vm.photo
        ? <img src={vm.photo} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : vm.initials}
    </div>
  );
}

export default function Sidebar({ collapsed, onToggle, profiles, onAddProfile, conversations, activeConvId, onConvClick, onConvDelete, onNewChat, user, onSignOut, accent }) {
  const [hoveredConv, setHoveredConv] = useState(null);
  const [hoveredProfile, setHoveredProfile] = useState(null);

  const logoMarkStyle = {
    width: '38px', height: '38px', borderRadius: '11px', background: accent,
    color: '#fff', fontFamily: "'Newsreader', serif", fontSize: '20px',
    display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto',
  };

  if (collapsed) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', padding: '16px 0' }}>
        <button onClick={onToggle} style={{ width: '34px', height: '34px', border: 'none', background: '#EAE3D7', borderRadius: '9px', color: '#6E7872', fontSize: '15px', cursor: 'pointer' }}>»</button>
        <div style={logoMarkStyle}>w</div>
        <div style={{ width: '30px', height: '1px', background: '#E1D9CC' }} />
        {profiles.map(p => (
          <button key={p.id} onClick={p.onClick} title={p.name} style={p.railAvatarStyle}>
            {p.photo ? <img src={p.photo} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : p.initials}
          </button>
        ))}
        <button onClick={onAddProfile} title="Add care profile" style={{ width: '38px', height: '38px', borderRadius: '50%', border: '1px dashed #CDBFAB', background: 'transparent', color: accent, fontSize: '18px', cursor: 'pointer', lineHeight: 1 }}>+</button>
        <div style={{ width: '30px', height: '1px', background: '#E1D9CC' }} />
        <button onClick={onNewChat} title="New conversation" style={{ width: '38px', height: '38px', borderRadius: '11px', border: '1px dashed #CDBFAB', background: 'transparent', color: accent, fontSize: '20px', cursor: 'pointer', lineHeight: 1 }}>+</button>
        <div style={{ flex: 1 }} />
        {CONNECTORS.map(c => (
          <div key={c.name} title={`${c.name} — Connected`} style={{ position: 'relative', width: '30px', height: '30px', borderRadius: '8px', background: '#EFEAE0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 600, color: '#8A9189' }}>
            <span>{c.initials}</span>
            <span style={{ position: 'absolute', right: '-2px', bottom: '-2px', width: '11px', height: '11px', borderRadius: '50%', background: '#2E8B6F', border: '2px solid #EDE8DF' }} />
          </div>
        ))}
        <button title="Settings" style={{ width: '34px', height: '34px', border: 'none', background: 'transparent', color: '#8A9189', fontSize: '17px', cursor: 'pointer' }}>⚙</button>
      </div>
    );
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '18px 16px 14px' }}>

      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '11px', padding: '2px 4px' }}>
        <div style={logoMarkStyle}>w</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'Newsreader', serif", fontSize: '21px', fontWeight: 500, letterSpacing: '-0.01em', lineHeight: 1, color: '#26322F' }}>Withcare</div>
          <div style={{ fontSize: '11.5px', color: '#9A9384', marginTop: '3px' }}>Healthcare, with care.</div>
        </div>
        <button onClick={onToggle} style={{ width: '30px', height: '30px', border: 'none', background: 'transparent', borderRadius: '8px', color: '#A39C8C', fontSize: '15px', cursor: 'pointer' }}>«</button>
      </div>

      {/* New chat */}
      <button onClick={onNewChat} style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '9px', width: '100%', padding: '11px 13px', borderRadius: '12px', border: '1px solid #DDD4C5', background: '#FBF9F4', color: '#3A4641', fontSize: '14px', fontWeight: 500, cursor: 'pointer', textAlign: 'left' }}>
        <span style={{ fontSize: '17px', color: accent, lineHeight: 1 }}>+</span> New conversation
      </button>

      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', margin: '18px -4px 0', padding: '0 4px' }}>

        {/* Care profiles */}
        <div style={{ fontSize: '10.5px', letterSpacing: '0.12em', fontWeight: 600, textTransform: 'uppercase', color: '#AAA291', padding: '0 4px 9px' }}>Care profiles</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
          {profiles.map(p => {
            const hovered = hoveredProfile === p.id;
            const nCtrls = (p.canEdit ? 1 : 0) + (p.canDelete ? 1 : 0);
            return (
              <div key={p.id} style={{ position: 'relative' }}
                onMouseEnter={() => setHoveredProfile(p.id)}
                onMouseLeave={() => setHoveredProfile(null)}>
                <button onClick={p.onClick} style={{ ...p.cardStyle, paddingRight: hovered && nCtrls ? `${12 + nCtrls * 26}px` : '11px' }}>
                  <Avatar vm={p} style={p.avatarStyle} />
                  <div style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
                    <div style={{ fontSize: '13.5px', fontWeight: 600, color: '#2C3833', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.isPet && <span style={{ marginRight: 4 }}>🐾</span>}{p.name}
                    </div>
                    <div style={{ fontSize: '11.5px', color: '#9A9485', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.relation}</div>
                  </div>
                  {p.active && !hovered && <span style={{ fontSize: '11px', fontWeight: 600, color: accent }}>Active</span>}
                </button>
                {hovered && nCtrls > 0 && (
                  <div style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: '4px' }}>
                    {p.canEdit && (
                      <button onClick={(e) => { e.stopPropagation(); p.onEdit(); }} title="Edit"
                        style={{ width: '22px', height: '22px', borderRadius: '6px', border: 'none', background: '#E0D8CC', color: '#6E7872', fontSize: '11px', cursor: 'pointer' }}>✎</button>
                    )}
                    {p.canDelete && (
                      <button onClick={(e) => { e.stopPropagation(); p.onDelete(); }} title="Delete"
                        style={{ width: '22px', height: '22px', borderRadius: '6px', border: 'none', background: '#E0D8CC', color: '#8A8273', fontSize: '13px', cursor: 'pointer' }}>×</button>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          <button onClick={onAddProfile}
            style={{ display: 'flex', alignItems: 'center', gap: '11px', width: '100%', padding: '9px 11px', borderRadius: '13px', border: '1px dashed #CDBFAB', background: 'transparent', cursor: 'pointer' }}>
            <div style={{ width: '34px', height: '34px', borderRadius: '50%', flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', color: accent, background: '#F1ECE2' }}>+</div>
            <span style={{ fontSize: '13.5px', fontWeight: 600, color: accent }}>Add care profile</span>
          </button>
        </div>

        {/* Conversations */}
        <div style={{ fontSize: '10.5px', letterSpacing: '0.12em', fontWeight: 600, textTransform: 'uppercase', color: '#AAA291', padding: '20px 4px 9px' }}>Conversations</div>

        {conversations.length === 0 ? (
          <div style={{ fontSize: '13px', color: '#B0A797', padding: '4px 8px' }}>No conversations yet</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            {conversations.map(c => {
              const isActive = activeConvId === c.id;
              const hovered  = hoveredConv === c.id;
              return (
                <div
                  key={c.id}
                  style={{ position: 'relative' }}
                  onMouseEnter={() => setHoveredConv(c.id)}
                  onMouseLeave={() => setHoveredConv(null)}
                >
                  <button
                    onClick={() => onConvClick(c.id)}
                    style={{
                      display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
                      width: '100%', textAlign: 'left',
                      padding: '9px 32px 9px 11px', borderRadius: '10px', cursor: 'pointer', border: 'none',
                      background: isActive ? '#EEF4F1' : hovered ? '#E8E3D9' : 'transparent',
                    }}
                  >
                    <span style={{
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      width: '100%', fontSize: '13.5px',
                      color: isActive ? '#1C7A6A' : '#5E665F',
                      fontWeight: isActive ? 600 : 500,
                    }}>
                      {c.title}
                    </span>
                    <span style={{ fontSize: '11px', color: '#A39C8C', marginTop: '2px' }}>
                      {c.profile_name !== 'You' ? `${c.profile_name} · ` : ''}{timeAgo(c.updated_at)}
                    </span>
                  </button>

                  {/* Delete button — appears on hover */}
                  {hovered && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onConvDelete(c.id); }}
                      title="Delete conversation"
                      style={{
                        position: 'absolute', right: '6px', top: '50%', transform: 'translateY(-50%)',
                        width: '22px', height: '22px', borderRadius: '6px', border: 'none',
                        background: '#E0D8CC', color: '#8A8273', fontSize: '13px', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        lineHeight: 1,
                      }}
                    >×</button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Connectors panel */}
      <div style={{ marginTop: '14px', border: '1px solid #E4DCCE', background: '#FBF9F4', borderRadius: '14px', padding: '12px 13px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '10.5px', letterSpacing: '0.1em', fontWeight: 700, textTransform: 'uppercase', color: '#8C9389' }}>Connected</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '11px', fontWeight: 600, color: '#2E8B6F' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#2E8B6F', boxShadow: '0 0 0 3px rgba(46,139,111,0.16)' }} />
            Live
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '9px' }}>
          {CONNECTORS.map(c => (
            <div key={c.name} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '26px', height: '26px', borderRadius: '7px', background: '#EEF4F1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, color: accent }}>{c.initials}</div>
              <span style={{ flex: 1, fontSize: '12.5px', color: '#3A4641', fontWeight: 500 }}>{c.name}</span>
              <span style={{ fontSize: '11px', color: '#2E8B6F', fontWeight: 600 }}>✓</span>
            </div>
          ))}
        </div>
      </div>

      {/* Signed-in user + sign out */}
      <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 6px' }}>
        <div style={{ width: '30px', height: '30px', borderRadius: '50%', flex: '0 0 auto', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#EDE7DB', color: '#8A8273', fontSize: '13px', fontWeight: 700 }}>
          {user?.picture ? <img src={user.picture} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : (user?.name || '?').trim().charAt(0).toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#3A4641', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.name || 'Signed in'}</div>
          {user?.email && <div style={{ fontSize: '11px', color: '#A39C8C', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.email}</div>}
        </div>
        <button onClick={onSignOut} title="Sign out"
          style={{ border: 'none', background: 'transparent', color: '#A39C8C', fontSize: '12.5px', fontWeight: 600, cursor: 'pointer' }}>
          Sign out
        </button>
      </div>
    </div>
  );
}
