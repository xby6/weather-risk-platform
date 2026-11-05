<template>
    <div class="screen-header flex-c" :class="{ geographic: screenStore.mapView === 'terrain' }">
        <div class="header-left flex-l">
            <span class="time-text">{{ currentTime }}</span>
        </div>
        <div class="header-center flex-c">
            <dv-decoration-8 class="dv-dec-8" :color="['#6f9dff', '#0d1828']" />
            <div class="title-box flex-c">
                <span class="title-text" title="辽宁电力气象智能网格预报预警信息系统">{{ screenStore.mapView === 'terrain' ? '辽宁电力气象 · 地理监测' : '辽宁电力气象智能网格预报预警信息系统' }}</span>
            </div>
            <dv-decoration-8 class="dv-dec-8" :reverse="true" :color="['#6f9dff', '#0d1828']" />
        </div>
        <div class="header-right flex-r">
            <div class="weather-info flex-c">
                <i class="iconfont icon-weather"></i>
                <span class="weather-text">{{ weatherText }}</span>
            </div>
            <a class="admin-link flex-c" :href="adminUrl" target="_blank" rel="noopener noreferrer">
                后台管理
            </a>
            <button class="notice-btn flex-c" type="button" @click="openNoticePanel">
                系统公告
                <span v-if="noticeCount > 0" class="notice-badge">{{ noticeCount }}</span>
            </button>
        </div>

        <Teleport to="body">
            <div v-if="noticeVisible" class="notice-mask" @click.self="closeNoticePanel">
            <div class="notice-panel">
                <div class="notice-panel-header">
                    <div>
                        <span class="notice-kicker">后台公告</span>
                        <strong>系统公告</strong>
                    </div>
                    <button class="notice-close" type="button" @click="closeNoticePanel">×</button>
                </div>

                <div v-if="noticeLoading" class="notice-empty">正在加载公告...</div>
                <div v-else-if="notices.length === 0" class="notice-empty">暂无系统公告</div>
                <div v-else class="notice-body">
                    <div class="notice-list">
                        <button
                            v-for="item in notices"
                            :key="item.noticeId"
                            class="notice-item"
                            :class="{ active: selectedNotice?.noticeId === item.noticeId, read: item.isRead }"
                            type="button"
                            @click="selectNotice(item)"
                        >
                            <span class="notice-type">{{ item.noticeTypeName || '公告' }}</span>
                            <span class="notice-title">{{ item.noticeTitle }}</span>
                            <span v-if="!item.isRead" class="notice-unread-dot" title="未读"></span>
                            <span class="notice-time">{{ formatNoticeTime(item.createTime) }}</span>
                        </button>
                    </div>
                    <div class="notice-detail">
                        <template v-if="selectedNotice">
                            <h3>{{ selectedNotice.noticeTitle }}</h3>
                            <div class="notice-meta">
                                <span>{{ selectedNotice.noticeTypeName || '公告' }}</span>
                                <span>{{ selectedNotice.createBy || '系统' }}</span>
                                <span>{{ selectedNotice.createTime || '-' }}</span>
                            </div>
                            <div class="notice-content" v-html="selectedNotice.noticeContent || '暂无内容'"></div>
                        </template>
                    </div>
                </div>
            </div>
            </div>
        </Teleport>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { apiGetSystemNotices, apiReadSystemNotice } from '@/api';
import { formatTime } from '@/utils/util';
import { fetchScreenAllData, screenStore } from '@/store/screenData';

interface NoticeItem {
    noticeId: number;
    noticeTitle: string;
    noticeTypeName?: string;
    noticeContent?: string;
    createBy?: string;
    createTime?: string;
    isRead?: boolean;
    readTime?: string;
}

const currentTime = ref('');
const noticeVisible = ref(false);
const noticeLoading = ref(false);
const notices = ref<NoticeItem[]>([]);
const selectedNotice = ref<NoticeItem | null>(null);
const unreadCount = ref(0);
const noticeCount = computed(() => unreadCount.value);
const weatherText = computed(() => {
    const parts = [screenStore.city, screenStore.weather, screenStore.temperatureRange].filter(Boolean);
    return parts.length ? parts.join(' ') : '暂无气象数据';
});
const adminUrl = `${window.location.protocol}//${window.location.hostname || '127.0.0.1'}/`;
let timer: number | null = null;

const loadNotices = async () => {
    noticeLoading.value = true;
    try {
        const res = await apiGetSystemNotices();
        notices.value = res.data?.rows || [];
        unreadCount.value = Number(res.data?.unreadCount || 0);
        const selectedId = selectedNotice.value?.noticeId;
        selectedNotice.value = notices.value.find(item => item.noticeId === selectedId) || notices.value[0] || null;
    } catch (error) {
        console.error('Failed to fetch system notices', error);
        notices.value = [];
        selectedNotice.value = null;
        unreadCount.value = 0;
    } finally {
        noticeLoading.value = false;
    }
};

const openNoticePanel = async () => {
    noticeVisible.value = true;
    await loadNotices();
    if (selectedNotice.value) {
        await selectNotice(selectedNotice.value);
    }
};

const selectNotice = async (item: NoticeItem) => {
    selectedNotice.value = item;
    if (item.isRead) return;
    try {
        const res = await apiReadSystemNotice(item.noticeId);
        item.isRead = true;
        item.readTime = res.data?.readTime || '';
        unreadCount.value = Number(res.data?.unreadCount ?? Math.max(unreadCount.value - 1, 0));
    } catch (error) {
        console.error('Failed to mark system notice as read', error);
    }
};

const closeNoticePanel = () => {
    noticeVisible.value = false;
};

const formatNoticeTime = (time?: string) => {
    if (!time) return '-';
    return String(time).slice(0, 10);
};

onMounted(() => {
    fetchScreenAllData();
    loadNotices();
    const days = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    timer = window.setInterval(() => {
        const now = new Date();
        const dateStr = formatTime(now, 'yyyy-MM-dd');
        const timeStr = formatTime(now, 'HH:mm:ss');
        const dayStr = days[now.getDay()];
        currentTime.value = `${dateStr} ${dayStr} ${timeStr}`;
    }, 1000);
});

onUnmounted(() => {
    if (timer) {
        clearInterval(timer);
    }
});
</script>

<style lang="scss" scoped>
@import '@/assets/scss/common/variables.scss';

.screen-header {
    width: 100%;
    height: 100%;
    position: relative;
    border: 1px solid rgba(112, 150, 205, 0.22);
    border-radius: 10px;
    background:
        linear-gradient(90deg, rgba(6, 13, 24, 0.74), rgba(15, 29, 49, 0.88), rgba(6, 13, 24, 0.74)),
        radial-gradient(circle at 50% 0%, rgba(79, 134, 255, 0.16), transparent 58%);
    box-shadow: inset 0 -1px 0 rgba(112, 150, 205, 0.20);

    .header-left {
        width: 20%;
        height: 100%;
        padding-left: 20px;

        .time-text {
            color: rgba(237, 247, 255, 0.76);
            font-size: 15px;
            font-family: 'Electronic', sans-serif;
            letter-spacing: 0.5px;
        }
    }

    .header-center {
        width: 60%;
        height: 100%;

        .dv-dec-8 {
            width: 170px;
            height: 44px;
            opacity: 0.86;
        }

        .title-box {
            width: auto;
            height: 100%;
            padding: 0 34px;
            position: relative;

            &::before {
                content: "";
                position: absolute;
                left: 12px;
                right: 12px;
                top: 13px;
                bottom: 13px;
                border: 1px solid rgba(112, 150, 205, 0.34);
                border-radius: 999px;
                background:
                    linear-gradient(90deg, rgba(79, 134, 255, 0.08), rgba(112, 150, 205, 0.16), rgba(216, 167, 79, 0.08));
                box-shadow: 0 0 22px rgba(79, 134, 255, 0.12);
            }

            .title-text {
                position: relative;
                font-size: 31px;
                font-weight: 700;
                color: #eef4ff;
                letter-spacing: 1.5px;
                text-shadow: 0 0 14px rgba(111, 157, 255, 0.34);
                white-space: nowrap;
            }
        }
    }

    .header-right {
        width: 20%;
        height: 100%;
        padding-right: 20px;
        justify-content: flex-end;

        .weather-info {
            max-width: 160px;
            margin-right: 10px;
            color: #eef4ff;
            font-size: 14px;

            .icon-weather {
                color: #d8a74f;
                margin-right: 5px;
                font-size: 18px;
            }

            .weather-text {
                color: rgba(237, 247, 255, 0.78);
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
        }

        .admin-link,
        .notice-btn {
            height: 30px;
            padding: 0 13px;
            border: 1px solid rgba(112, 150, 205, 0.42);
            border-radius: 999px;
            color: #e7f0ff;
            font-size: 14px;
            cursor: pointer;
            background: rgba(79, 134, 255, 0.10);
            transition: all 0.3s;
            white-space: nowrap;
            text-decoration: none;

            &:hover {
                background: rgba(79, 134, 255, 0.18);
                border-color: rgba(111, 157, 255, 0.65);
            }
        }

        .admin-link {
            margin-right: 8px;
        }

        .notice-btn {
            position: relative;
            font-family: inherit;
        }

        .notice-badge {
            min-width: 16px;
            height: 16px;
            padding: 0 4px;
            margin-left: 5px;
            border-radius: 999px;
            background: #d8a74f;
            color: #07121f;
            font-size: 11px;
            line-height: 16px;
            font-weight: 700;
        }
    }
}

.screen-header.geographic {
    border: 0;
    border-bottom: 1px solid #7b897b25;
    .header-center { order: -1; width: auto; margin-right: auto; justify-content: flex-start; }
    .header-center .dv-dec-8, .header-center .title-box::before { display: none; }
    .header-center .title-box { padding: 0; }
    .header-center .title-box .title-text { font-size: 22px; color: #e5eadf; letter-spacing: .5px; text-shadow: none !important; }
    .header-left { width: auto; margin-right: 30px; }
    .header-left .time-text { font-size: 12px; color: #879387; }
    .header-right { width: auto; padding-right: 0; }
    .header-right .admin-link, .header-right .notice-btn { border-color: #80917e40; background: #50614a15; border-radius: 4px; font-size: 12px; }
}

.notice-mask {
    position: fixed !important;
    inset: 0;
    z-index: 2147483000;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(2, 8, 15, 0.62);
    backdrop-filter: blur(6px);
    pointer-events: auto;
}

.notice-panel {
    position: relative;
    z-index: 1;
    width: min(860px, calc(100vw - 64px));
    height: min(560px, calc(100vh - 80px));
    border: 1px solid rgba(112, 150, 205, 0.28);
    border-radius: 12px;
    background:
        linear-gradient(180deg, rgba(11, 25, 43, 0.96), rgba(5, 12, 24, 0.98)),
        radial-gradient(circle at 30% 0%, rgba(79, 134, 255, 0.18), transparent 45%);
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.46);
    color: #eef4ff;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.notice-panel-header {
    height: 64px;
    padding: 0 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(112, 150, 205, 0.16);

    strong {
        display: block;
        margin-top: 3px;
        font-size: 20px;
    }
}

.notice-kicker {
    color: rgba(216, 167, 79, 0.9);
    font-size: 12px;
    letter-spacing: 2px;
}

.notice-close {
    width: 32px;
    height: 32px;
    border: 1px solid rgba(112, 150, 205, 0.26);
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.04);
    color: #e7f0ff;
    cursor: pointer;
    font-size: 22px;
    line-height: 28px;
}

.notice-body {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 310px minmax(0, 1fr);
}

.notice-list {
    min-height: 0;
    overflow-y: auto;
    padding: 12px;
    border-right: 1px solid rgba(112, 150, 205, 0.14);
}

.notice-item {
    width: 100%;
    min-height: 76px;
    margin-bottom: 10px;
    padding: 10px 12px;
    border: 1px solid rgba(112, 150, 205, 0.14);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.025);
    color: inherit;
    cursor: pointer;
    text-align: left;
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 6px 8px;

    &.active,
    &:hover {
        border-color: rgba(111, 157, 255, 0.48);
        background: rgba(79, 134, 255, 0.10);
    }

    &.read {
        opacity: 0.72;
    }
}

.notice-type {
    padding: 1px 7px;
    border-radius: 999px;
    background: rgba(216, 167, 79, 0.14);
    color: #d8a74f;
    font-size: 12px;
}

.notice-title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 14px;
    font-weight: 700;
}

.notice-time {
    grid-column: 1 / -1;
    color: #9cacc2;
    font-size: 12px;
}

.notice-unread-dot {
    width: 8px;
    height: 8px;
    margin-top: 5px;
    border-radius: 50%;
    background: #ff6b6b;
    box-shadow: 0 0 8px rgba(255, 107, 107, 0.72);
}

.notice-detail {
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    padding: 18px 20px;

    h3 {
        margin: 0 0 8px;
        font-size: 22px;
        line-height: 1.35;
    }
}

.notice-meta {
    display: flex;
    gap: 12px;
    color: #9cacc2;
    font-size: 12px;
    padding-bottom: 14px;
    margin-bottom: 14px;
    border-bottom: 1px solid rgba(112, 150, 205, 0.14);
}

.notice-content {
    color: rgba(237, 247, 255, 0.86);
    font-size: 14px;
    line-height: 1.8;
    word-break: break-word;

    :deep(p) {
        margin: 0 0 10px;
    }
}

.notice-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(220, 236, 255, 0.62);
    font-size: 15px;
}

.flex-l {
    display: flex;
    align-items: center;
}

.flex-c {
    display: flex;
    align-items: center;
    justify-content: center;
}

.flex-r {
    display: flex;
    align-items: center;
    justify-content: flex-end;
}
</style>
