import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.core.paginator import Paginator

from .models import ECGUpload
from .forms import ECGUploadForm, ECGUpdateForm
from .services import analyze_ecg
import json


def home(request):
    return render(request, 'heartguard/home.html')


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('upload_list')
    else:
        form = UserCreationForm()
    return render(request, 'heartguard/register.html', {'form': form})


@login_required
def upload_create(request):
    # --- 10 UPLOAD LIMIT CHECK ---
    if ECGUpload.objects.filter(user=request.user).count() >= 10:
        messages.error(request, 'Upload limit reached: You can only upload a maximum of 10 ECGs.')
        return redirect('upload_list')

    if request.method == 'POST':
        form = ECGUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.user = request.user

            # Handle file presence
            if 'file' in request.FILES:
                upload.original_filename = request.FILES['file'].name
            else:
                upload.original_filename = 'Clinical Data Only'

            upload.status = 'PROCESSING'
            upload.save()
            try:
                analyze_ecg(upload)
                upload.status = 'COMPLETED'
                upload.save()
                messages.success(request, 'Analysis completed successfully!')
            except Exception as e:
                upload.status = 'FAILED'
                upload.error_message = str(e)
                upload.save()
                messages.error(request, f'Analysis failed: {e}')
            return redirect('upload_detail', pk=upload.pk)
    else:
        form = ECGUploadForm()
    return render(request, 'heartguard/upload_create.html', {'form': form})


@login_required
def clinical_create(request):
    # --- 10 UPLOAD LIMIT CHECK ---
    if ECGUpload.objects.filter(user=request.user).count() >= 10:
        messages.error(request, 'Upload limit reached: You can only upload a maximum of 10 records.')
        return redirect('upload_list')

    if request.method == 'POST':
        form = ECGUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.user = request.user
            if 'file' in request.FILES:
                upload.original_filename = request.FILES['file'].name
            else:
                upload.original_filename = 'Clinical Data Only'
            upload.status = 'PROCESSING'
            upload.save()
            try:
                analyze_ecg(upload)
                upload.status = 'COMPLETED'
                upload.save()
                messages.success(request, 'Clinical assessment completed!')
            except Exception as e:
                upload.status = 'FAILED'
                upload.error_message = str(e)
                upload.save()
                messages.error(request, f'Assessment failed: {e}')
            return redirect('upload_detail', pk=upload.pk)
    else:
        form = ECGUploadForm()
    return render(request, 'heartguard/clinical_create.html', {'form': form})


@login_required
def upload_list(request):
    # Base query for pagination (newest first here)
    qs = ECGUpload.objects.filter(user=request.user).select_related('result').order_by('-created_at')
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get('page'))

    # --- CHART DATA PREPARATION ---
    # Fetch all uploads in chronological order (oldest to newest) for the chart
    chronological_uploads = ECGUpload.objects.filter(user=request.user).select_related('result').order_by('created_at')
    
    dates = []
    risk_scores = []

    for up in chronological_uploads:
        dates.append(up.created_at.strftime('%b %d')) # e.g., "Oct 12"
        
        # Check if the result exists to extract the heart attack percentage
        if hasattr(up, 'result') and up.result:
            # Note: I'm using heart_attack_percent based on the previous template. 
            risk_scores.append(getattr(up.result, 'heart_attack_percent', 0))
        else:
            risk_scores.append(0)

    context = {
        'page': page,
        'chart_dates': json.dumps(dates),
        'chart_risks': json.dumps(risk_scores),
    }
    return render(request, 'heartguard/upload_list.html', context)




@login_required
def upload_detail(request, pk):
    # Get current upload
    upload = get_object_or_404(ECGUpload, pk=pk, user=request.user)
    result = getattr(upload, 'result', None)
    
    # --- START CHART LOGIC ---
    # Fetch last 10 completed uploads for this user to show progress
    history = ECGUpload.objects.filter(
        user=request.user, 
        status='COMPLETED'
    ).select_related('result').order_by('created_at')[:10]

    total_uploads = history.count()
    
    # Prepare data lists for JavaScript
    chart_dates = []
    chart_risks = []
    
    for item in history:
        if hasattr(item, 'result'):
            # Format date for labels (e.g., "Oct 12")
            chart_dates.append(item.created_at.strftime("%b %d"))
            # Get heart attack probability as a percentage
            chart_risks.append(round(item.result.heart_attack_probability * 100, 1))

    # --- END CHART LOGIC ---

    context = {
        'upload': upload,
        'result': result,
        'total_uploads': total_uploads,
        'chart_dates': json.dumps(chart_dates), # Must be JSON string for JS
        'chart_risks': json.dumps(chart_risks),  # Must be JSON string for JS
    }
    return render(request, 'heartguard/upload_detail.html', context)


@login_required
def upload_update(request, pk):
    upload = get_object_or_404(ECGUpload, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ECGUpdateForm(request.POST, instance=upload)
        if form.is_valid():
            form.save()
            messages.success(request, 'Updated.')
            return redirect('upload_detail', pk=pk)
    else:
        form = ECGUpdateForm(instance=upload)
    return render(request, 'heartguard/upload_update.html', {'form': form, 'upload': upload})


@login_required
def upload_delete(request, pk):
    upload = get_object_or_404(ECGUpload, pk=pk, user=request.user)
    if request.method == 'POST':
        upload.file.delete(save=False)
        upload.delete()
        messages.success(request, 'Deleted.')
        return redirect('upload_list')
    return render(request, 'heartguard/upload_delete.html', {'upload': upload})