from .classes.SmsCallback import *
import datetime
import time
import pytz
import requests
import requests
import json
from AutoserviceDashboardApi.database.models import *

def my_scheduled_job():
    voicemail_tbl = tbl_voicemail.objects.filter(status__lt=2, type=2, alert_to_manager=0).order_by(
        "-time")
    for voicemail_obj in voicemail_tbl:
        # --------- change date.now() formate ---------- #
        timeZ_Ce = pytz.timezone('US/Central')
        fmt = '%Y-%m-%d %H:%M:%S'
        today_date1 = datetime.datetime.now(timeZ_Ce).strftime(fmt)
        today_date_frmt = datetime.datetime.strptime(str(today_date1), "%Y-%m-%d %H:%M:%S")
        # --------- change db_date formate ---------- #        
        voice_time = voicemail_obj.time.strftime("%Y-%m-%d %H:%M:%S")
        db_time = datetime.datetime.strptime(str(voice_time), "%Y-%m-%d %H:%M:%S")
        # --------- check advisor.configEscalationOnOff && voicemail.cronProcess=1 ---------- #        
        advisor_obj = tbl_advisor.objects.filter(phone_number=voicemail_obj.advisor_phone).first()
        company_obj = tbl_company.objects.get(pk=advisor_obj.company_id)
        if advisor_obj.configEscalationOnOff == 1 && voicemail_obj.cronProcess == 1:
            # --------- send advisor email ---------- #        
            if voicemail_obj.advisor_sent_count == 0:
                 response_tpl_map = {
                    "advisor_name": advisor_obj.name,
                    "caller_name": voicemail_obj.caller_name,
                    "caller_phone": voicemail_obj.caller_phone,
                    "message": voicemail_obj.message,
                    "ok_text": voicemail_obj.ok_text
                }
                                                                     response_tpl_map)
                #----------- for short url ------#
                # obj = UrlShortenTinyurl() 
                # r_url = obj.shorten("http://dashboard.autoservice.ai/v/" + str(
                #                                  voicemail_obj.id) + "/0")

                response_tpl = atsd_voicemail.updateResponseTemplate(advisor_obj.advisor_response_template,
                r_tpl = response_tpl.replace("{{responseLink}}","https://d.autoservice.ai/v/" + str(
                                                 voicemail_obj.id))
                glb_twilio.sendSms(company_obj.twilio_account_sid,
                                   company_obj.twilio_auth_token,
                                   company_obj.twilio_phone_number,
                                   voicemail_obj.advisor_phone,
                                   r_tpl)
                glb_email.sendEmail(from_str=" AutoService.AI",
                                    src_email=GMAIL_ACCOUNT["email"],
                                    src_pwd=GMAIL_ACCOUNT["password"],
                                    dest_email=advisor_obj.email,
                                    subject=" Allio: You Got Voicemail",
                                    content=r_tpl,
                                    smtp_server_domain="premium70.web-hosting.com",
                                    smtp_server_port=587)
                # Increment advisorSentCount and save
                voicemail_obj.advisor_sent_count = 1
                voicemail_obj.save()
            # --------- send buddies email ---------- #        
            elif voicemail_obj.advisor_sent_count == 1 && (today_date_frmt - db_time) >= datetime.timedelta(
                minutes=voicemail_obj.delay_time) and voicemail_obj.alert_to_manager == 0:
                response_tpl_map = {
                    "advisor_name": advisor_obj.name,
                    "caller_name": voicemail_obj.caller_name,
                    "caller_phone": voicemail_obj.caller_phone,
                    "message": voicemail_obj.message,
                    "ok_text": voicemail_obj.ok_text
                }
                response_tpl = atsd_voicemail.updateResponseTemplate(advisor_obj.advisor_response_template,
                                                                     response_tpl_map)
                buddy_list = json.loads(advisor_obj.buddy_list)
                idx = 1
                for buddy in buddy_list:
                    # obj = UrlShortenTinyurl() 
                    # r_url = obj.shorten("http://dashboard.autoservice.ai/voicemail/" + str(
                    #                          voicemail_obj.id) + "/" + str(idx))

                    r_tpl = response_tpl.replace("{{responseLink}}","https://d.autoservice.ai/v/" + str(
                                             voicemail_obj.id))
                   
                    # if sms_flag == True:
                    glb_twilio.sendSms(company_obj.twilio_account_sid,
                                       company_obj.twilio_auth_token,
                                       company_obj.twilio_phone_number,
                                       buddy["phone_number"],
                                       "Allio: Second Notification for: " + str(
                                            advisor_obj.name) + r_tpl)

                    # if email_flag == True:
                    glb_email.sendEmail(from_str=" AutoService.AI",
                                        src_email=GMAIL_ACCOUNT["email"],
                                        src_pwd=GMAIL_ACCOUNT["password"],
                                        dest_email=buddy["email"],
                                        subject=" Allio: Second Notification for: " + str(
                                            advisor_obj.name),
                                        content=r_tpl,
                                        smtp_server_domain="premium70.web-hosting.com",
                                        smtp_server_port=587)
                idx += 1
                voicemail_obj.advisor_sent_count = 2
                voicemail_obj.save()            
                # --------copy advisor
                glb_twilio.sendSms(company_obj.twilio_account_sid,
                                   company_obj.twilio_auth_token,
                                   company_obj.twilio_phone_number,
                                   voicemail_obj.advisor_phone,
                                   "Allio: Second Notification" + r_tpl)
                glb_email.sendEmail(from_str=" AutoService.AI",
                                    src_email=GMAIL_ACCOUNT["email"],
                                    src_pwd=GMAIL_ACCOUNT["password"],
                                    dest_email=advisor_obj.email,
                                    subject=" Allio: Second Notification",
                                    content=r_tpl,
                                    smtp_server_domain="premium70.web-hosting.com",
                                    smtp_server_port=587)
            # --------- send manager email ---------- #        
            elif voicemail_obj.alert_to_manager == 0 && (today_date_frmt - db_time) >= (2 * datetime.timedelta(
                minutes=voicemail_obj.delay_time)):
                response_tpl_map = {
                    "advisor_name": advisor_obj.name,
                    "caller_name": voicemail_obj.caller_name,
                    "caller_phone": voicemail_obj.caller_phone,
                    "message": voicemail_obj.message,
                    "ok_text": voicemail_obj.ok_text
                }
                response_tpl = atsd_voicemail.updateResponseTemplate(advisor_obj.manager_response_template,
                                                                     response_tpl_map)
                #----------- for short url ------#
                # obj = UrlShortenTinyurl() 
                # r_url = obj.shorten("http://dashboard.autoservice.ai/v/" + str(
                #                                  voicemail_obj.id) + "/0")

                r_tpl = response_tpl.replace("{{responseLink}}","https://d.autoservice.ai/v/" + str(
                                                 voicemail_obj.id))

                glb_twilio.sendSms(company_obj.twilio_account_sid,
                                   company_obj.twilio_auth_token,
                                   company_obj.twilio_phone_number,
                                   advisor_obj.alert_phone_number,
                                   r_tpl)
                glb_email.sendEmail(from_str="AutoService.AI",
                                    src_email=GMAIL_ACCOUNT["email"],
                                    src_pwd=GMAIL_ACCOUNT["password"],
                                    dest_email=advisor_obj.alert_email,
                                    subject=" Allio: Final Notification - " + str(advisor_obj.name),
                                    content=r_tpl,
                                    smtp_server_domain="premium70.web-hosting.com",
                                    smtp_server_port=587)
                # Increment advisorSentCount and save
                voicemail_obj.alert_to_manager = 1
                voicemail_obj.save()
                # --------copy advisor
                glb_twilio.sendSms(company_obj.twilio_account_sid,
                                   company_obj.twilio_auth_token,
                                   company_obj.twilio_phone_number,
                                   voicemail_obj.advisor_phone,
                                   r_tpl)
                glb_email.sendEmail(from_str=" AutoService.AI",
                                    src_email=GMAIL_ACCOUNT["email"],
                                    src_pwd=GMAIL_ACCOUNT["password"],
                                    dest_email=advisor_obj.email,
                                    subject=" Allio: Final Notification",
                                    content=r_tpl,
                                    smtp_server_domain="premium70.web-hosting.com",
                                    smtp_server_port=587)
            return Response({}, status=HttpResponse200)
        except Exception as e:
            return Response({}, status=HttpResponse500)
    