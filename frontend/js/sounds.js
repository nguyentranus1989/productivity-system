// frontend/js/sounds.js
class SoundManager {
    constructor() {
        this.sounds = {
            achievement: new Audio('assets/sounds/achievement.mp3'),
            levelUp: new Audio('assets/sounds/level-up.mp3'),
            newRecord: new Audio('assets/sounds/new-record.mp3'),
            tick: new Audio('assets/sounds/tick.mp3')
        };
        
        // Pre-load sounds
        Object.values(this.sounds).forEach(sound => {
            sound.load();
            sound.volume = 0.3;
        });
    }
    
    play(soundName) {
        if (this.sounds[soundName]) {
            this.sounds[soundName].currentTime = 0;
            this.sounds[soundName].play().catch(e => console.log('Sound play failed:', e));
        }
    }
}

const soundManager = new SoundManager();