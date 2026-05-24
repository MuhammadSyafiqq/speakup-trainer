from flask import Blueprint, render_template, jsonify, request, abort
from flask_login import login_required, current_user
from models.session import PracticeSession
from extensions import db
import os

history_bp = Blueprint('history', __name__)

@history_bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    category_filter = request.args.get('category', '')

    query = PracticeSession.query.filter_by(
        user_id=current_user.id,
        status='completed'
    )

    if category_filter:
        query = query.filter_by(category=category_filter)

    # error_out=False → halaman kosong return 200, bukan 404
    sessions = query.order_by(
        PracticeSession.created_at.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    return render_template('history.html', sessions=sessions, category_filter=category_filter)


@history_bp.route('/history/chart-data')
@login_required
def chart_data():
    category_filter = request.args.get('category', '')

    sessions = PracticeSession.query.filter_by(
        user_id=current_user.id,
        status='completed'
    )

    if category_filter:
        sessions = sessions.filter_by(category=category_filter)

    sessions = sessions.order_by(
        PracticeSession.created_at.asc()
    ).limit(20).all()

    data = {
        'labels': [],
        'scores_total': [],
        'scores_clarity': [],
        'scores_structure': [],
        'scores_confidence': [],
        'scores_relevance': [],
        'scores_vocabulary': [],
        'scores_fluency': [],
        'categories': [],
        'titles': [],
    }

    for s in sessions:
        data['labels'].append(s.created_at.strftime('%d/%m/%Y'))
        data['scores_total'].append(s.score_total or 0)
        data['scores_clarity'].append(s.score_clarity or 0)
        data['scores_structure'].append(s.score_structure or 0)
        data['scores_confidence'].append(s.score_confidence or 0)
        data['scores_relevance'].append(s.score_relevance or 0)
        data['scores_vocabulary'].append(s.score_vocabulary or 0)
        data['scores_fluency'].append(s.score_fluency or 0)
        data['categories'].append(s.category)
        data['titles'].append(s.title)

    all_scores = [s.score_total for s in sessions if s.score_total]
    data['stats'] = {
        'total_sessions': len(sessions),
        'avg_score': round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
        'best_score': max(all_scores) if all_scores else 0,
        'latest_score': all_scores[-1] if all_scores else 0,
        'improvement': round(all_scores[-1] - all_scores[0], 1) if len(all_scores) >= 2 else 0
    }

    return jsonify(data)


@history_bp.route('/history/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = db.session.get(PracticeSession, session_id)
    if session is None:
        abort(404)

    if session.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Akses ditolak'}), 403

    if session.audio_path and os.path.exists(session.audio_path):
        os.remove(session.audio_path)

    db.session.delete(session)
    db.session.commit()
    return jsonify({'success': True})